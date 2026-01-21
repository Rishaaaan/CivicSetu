from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import firebase_admin
from firebase_admin import auth as fb_auth
from .firebase import db, create_user as fs_create_user, create_report as fs_create_report
from .firebase import increment_reports as fs_increment_reports
from google.cloud.firestore import Client
from datetime import datetime, timedelta
from django.utils import timezone
import logging
from typing import Optional, Tuple
import os
from collections import Counter, defaultdict

try:
    from gradio_client import Client as GradioClient, handle_file
except Exception:
    GradioClient = None  # Will log error if used without being installed
    handle_file = None

logger = logging.getLogger(__name__)
if not logger.handlers:
    # Basic configuration if not already configured by Django
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')

def _ensure_aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (using current timezone) for safe comparisons."""
    try:
        if isinstance(dt, datetime) and dt.tzinfo is None:
            return timezone.make_aware(dt, timezone.get_current_timezone())
    except Exception:
        pass
    return dt

# -----------------------------
# JoyCaption Integration
# -----------------------------
_JOY_SPACE = "fancyfeast/joy-caption-alpha-two"
_JOY_API = "/stream_chat"
_listener_started = False
_listener_unsubscribe = None

# Gemini API (v1)
try:
    from google import genai  # modern client
except Exception:
    genai = None

def _get_joy_caption(image_url: str) -> Optional[Tuple[str, str]]:
    """
    Send image to JoyCaption Space and return (prompt_used, caption_text).
    Returns None if the call fails.
    """
    if GradioClient is None or handle_file is None:
        logger.error("gradio_client is not installed. Please ensure 'gradio_client' is in requirements and installed.")
        return None
    try:
        # Optional Hugging Face token support (environment var or Django settings)
        hf_token = (
            os.environ.get('HUGGINGFACEHUB_API_TOKEN') or
            getattr(settings, 'HUGGINGFACEHUB_API_TOKEN', None) or
            getattr(settings, 'HF_TOKEN', None)
        )
        if hf_token:
            client = GradioClient(_JOY_SPACE, hf_token=hf_token)
        else:
            client = GradioClient(_JOY_SPACE)
        logger.info("Calling JoyCaption API for image URL: %s", image_url)
        result = client.predict(
            input_image=handle_file(image_url),
            caption_type="Descriptive",
            caption_length="long",
            extra_options=[],
            name_input="",
            custom_prompt="",
            api_name=_JOY_API
        )
        # result is a tuple: (prompt_used, caption_text)
        if isinstance(result, (list, tuple)) and len(result) >= 2:
            prompt_used, caption_text = result[0], result[1]
            logger.info("JoyCaption call succeeded. Caption length=%d", len(caption_text or ""))
            return prompt_used, caption_text
        logger.error("Unexpected JoyCaption response format: %r", result)
        return None
    except Exception as e:
        logger.exception("JoyCaption API call failed: %s", e)
        return None

def _on_reports_snapshot(col_snapshot, changes, read_time):
    """Firestore snapshot callback for the 'reports' collection."""
    try:
        for change in changes:
            try:
                if getattr(change, 'type', None) and change.type.name == 'ADDED':
                    doc = change.document
                    data = doc.to_dict() or {}
                    image_url = data.get('image_url') or data.get('image')
                    image_caption = data.get('image_caption')
                    report_id = data.get('report_id') or doc.id
                    if image_url and not image_caption:
                        logger.info("New report with image detected (report_id=%s). Requesting caption...", report_id)
                        res = _get_joy_caption(image_url)
                        if res is None:
                            logger.error("Caption generation failed for report_id=%s", report_id)
                            continue
                        prompt_used, caption_text = res
                        try:
                            db.collection('reports').document(doc.id).update({
                                'image_caption': caption_text,
                                'joy_prompt_used': prompt_used,
                                'caption_generated_at': timezone.now(),
                            })
                            logger.info("Updated image_caption for report_id=%s", report_id)
                        except Exception as uex:
                            logger.exception("Failed to update image_caption for report_id=%s: %s", report_id, uex)
            except Exception:
                logger.exception("Failed processing a report change event")
    except Exception:
        logger.exception("Error in reports snapshot callback")

def start_report_caption_listener():
    """
    Start a Firestore collection listener for 'reports' to auto-generate image captions.
    Safe to call multiple times; will only start once per process.
    """
    global _listener_started, _listener_unsubscribe
    if _listener_started:
        return
    try:
        logger.info("Starting Firestore listener for report image captions...")
        _listener_unsubscribe = db.collection('reports').on_snapshot(_on_reports_snapshot)
        _listener_started = True
        logger.info("Report caption listener started.")
    except Exception:
        logger.exception("Failed to start report caption listener")

# Do NOT start Firestore listeners at import time in production workers.
# They will be started lazily from the first dashboard request.

def root_redirect(request):
    if request.session.get('admin_user'):
        return redirect('admin_dashboard')
    return redirect('login')

def login_page(request):
    # Simple login page that uses Firebase Web SDK to get ID token
    if request.session.get('admin_user'):
        return redirect('admin_dashboard')
    return render(request, 'login_admin.html')

def register_page(request):
    # Registration page (requires Firebase Auth token client-side to authorize)
    preferred_theme = request.COOKIES.get('cc_theme', 'light')
    return render(request, 'register_user.html', { 'preferred_theme': preferred_theme })

import json

@csrf_exempt
@require_POST
def verify_token(request):
    """
    Receives Firebase ID token from frontend, verifies it, and checks Firestore role=admin.
    On success, sets session and returns JSON.
    """
    id_token = None
    
    # Try JSON body
    if request.content_type == "application/json":
        try:
            body = json.loads(request.body.decode("utf-8"))
            id_token = body.get("idToken")
        except Exception:
            pass

    # Fallback to POST form or Authorization header
    if not id_token:
        id_token = request.POST.get('idToken') or (request.headers.get('Authorization') or '').replace('Bearer ', '')

    if not id_token:
        return JsonResponse({'ok': False, 'error': 'missing_id_token'}, status=400)

    try:
        decoded = fb_auth.verify_id_token(id_token)
        uid = decoded['uid']
    except Exception:
        return JsonResponse({'ok': False, 'error': 'invalid_token'}, status=401)

    # Check Firestore role
    email = decoded.get('email')
    role = None
    department = None
    user_doc = None
    try:
        if email:
            q = db.collection('users').where('email', '==', email).limit(1).stream()
            for d in q:
                user_doc = d
                break
        if user_doc:
            data = user_doc.to_dict()
            role = data.get('role')
            department = data.get('department')
    except Exception:
        pass

    # Allow admin and department_head roles
    if role not in ('admin', 'department_head'):
        return JsonResponse({'ok': False, 'error': 'not_staff'}, status=403)

    # Set session
    request.session['admin_user'] = {
        'uid': uid,
        'email': email,
        'name': decoded.get('name'),
        'role': role,
        'department': department,
    }
    return JsonResponse({'ok': True, 'role': role, 'department': department})

@csrf_exempt
@require_POST
def auth_create_user(request):
    """
    Creates a Firebase Auth user and a Firestore user profile.
    Requires a valid Firebase ID token in POST idToken or Authorization header.
    - If requester has role=admin, they can create admin or citizen users.
    - If requester is not admin, only 'citizen' creation is allowed.
    """
    id_token = request.POST.get('idToken') or (request.headers.get('Authorization') or '').replace('Bearer ', '')
    if not id_token:
        return JsonResponse({'ok': False, 'error': 'missing_id_token'}, status=400)

    try:
        decoded = fb_auth.verify_id_token(id_token)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'invalid_token'}, status=401)

    requester_email = decoded.get('email')
    requester_role = None
    try:
        if requester_email:
            q = db.collection('users').where('email', '==', requester_email).limit(1).stream()
            for d in q:
                requester_role = d.to_dict().get('role')
                break
    except Exception:
        pass

    # Incoming fields
    name = request.POST.get('name')
    email = request.POST.get('email')
    password = request.POST.get('password')
    role = request.POST.get('role', 'citizen')
    department = request.POST.get('department')
    city = request.POST.get('city') or 'Unknown'

    if not all([name, email, password]):
        return JsonResponse({'ok': False, 'error': 'missing_fields'}, status=400)

    # Enforce permissions: only admins can create admins
    if role == 'admin' and requester_role != 'admin':
        return JsonResponse({'ok': False, 'error': 'forbidden_create_admin'}, status=403)

    try:
        # Create Firebase Auth user
        user_record = fb_auth.create_user(
            email=email,
            password=password,
            display_name=name,
            email_verified=False,
            disabled=False,
        )
        # Create Firestore profile
        user_id = fs_create_user(name=name, email=email, role=role, department=department, city=city, auth_uid=user_record.uid)
        return JsonResponse({'ok': True, 'user_id': user_id, 'auth_uid': user_record.uid})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': 'create_user_failed'}, status=500)

def logout_view(request):
    request.session.flush()
    return redirect('login')

def admin_dashboard(request):
    if not request.session.get('admin_user'):
        return redirect('login')
    # Ensure the caption listener is running
    try:
        start_report_caption_listener()
    except Exception:
        logger.exception("Failed ensuring report caption listener is running")
    ctx = {
        'current_user': request.session.get('admin_user') or {}
    }
    print(ctx)
    return render(request, 'civic_admin_dashboard_DarkTheme.html', ctx)

def _require_admin(request):
    # Strictly require admin role for sensitive endpoints
    user = request.session.get('admin_user') or {}
    return bool(user and user.get('role') == 'admin')


def _get_session_role(request):
    user = request.session.get('admin_user') or {}
    return user.get('role')


def _get_session_department(request):
    user = request.session.get('admin_user') or {}
    return user.get('department')


def _require_staff(request):
    # Allow both admin and department_head to access dashboard/report views
    user = request.session.get('admin_user') or {}
    return bool(user and (user.get('role') in ('admin', 'department_head')))


def _serialize_doc(doc):
    data = doc.to_dict()
    # Normalize timestamps
    for k, v in list(data.items()):
        if hasattr(v, 'isoformat'):
            try:
                data[k] = v.isoformat()
            except Exception:
                pass
    data['id'] = doc.id
    # Default priority mapping if missing
    if 'priority' not in data:
        status = data.get('status', 'pending')
        data['priority'] = 'high' if status == 'pending' else 'medium'
    # Attempt to parse lat/lng from 'location' if stored as "lat,lng"
    loc = data.get('location')
    if isinstance(loc, str) and ',' in loc:
        try:
            lat_s, lng_s = loc.split(',')
            data['lat'] = float(lat_s.strip())
            data['lng'] = float(lng_s.strip())
        except Exception:
            pass
    # Support Firestore GeoPoint
    if loc is not None and hasattr(loc, 'latitude') and hasattr(loc, 'longitude'):
        try:
            data['lat'] = float(loc.latitude)
            data['lng'] = float(loc.longitude)
        except Exception:
            pass
    # Fallbacks for UI fields
    if not data.get('title'):
        kw = data.get('keywords') or []
        data['title'] = ', '.join(kw) if isinstance(kw, list) and kw else f"{data.get('department','report').title()} report"
    if not data.get('user_description') and data.get('description'):
        data['user_description'] = data['description']
    if not data.get('image_url') and data.get('image'):
        data['image_url'] = data['image']
    return data


def get_reports(request):
    # Allow both admin and department head to fetch reports
    if not _require_staff(request):
        return HttpResponseForbidden('Auth required')
    try:
        # Recent first
        q = db.collection('reports').order_by('created_at', direction='DESCENDING').limit(200)
        raw_docs = list(q.stream())
        items = [_serialize_doc(d) for d in raw_docs]

        # If department head, restrict to their department only (case-insensitive)
        role = _get_session_role(request)
        if role == 'department_head':
            dept = (_get_session_department(request) or '').strip().lower()
            if dept:
                items = [it for it in items if str(it.get('department') or '').strip().lower() == dept]

        # Enrich reporter_name
        user_ids = {it.get('user_id') for it in items if it.get('user_id')}
        user_cache = {}
        for uid in user_ids:
            try:
                udoc = db.collection('users').document(uid).get()
                if udoc.exists:
                    user_cache[uid] = udoc.to_dict()
            except Exception:
                pass
        for it in items:
            uid = it.get('user_id')
            if uid and uid in user_cache:
                it['reporter_name'] = user_cache[uid].get('name')
        return JsonResponse({'ok': True, 'items': items})
    except Exception:
        return JsonResponse({'ok': False, 'error': 'failed_to_fetch'})

@require_POST
def api_create_user(request):
    if not _require_admin(request):
        return HttpResponseForbidden('Auth required')
    name = request.POST.get('name')
    email = request.POST.get('email')
    role = request.POST.get('role', 'citizen')
    department = request.POST.get('department')
    city = request.POST.get('city') or 'Unknown'
    if not name or not email:
        return JsonResponse({'ok': False, 'error': 'missing_fields'}, status=400)
    user_id = fs_create_user(name=name, email=email, role=role, department=department, city=city)
    return JsonResponse({'ok': True, 'user_id': user_id})

@require_POST
def api_create_report(request):
    if not _require_admin(request):
        return HttpResponseForbidden('Auth required')
    user_id = request.POST.get('user_id')
    department = request.POST.get('department')
    city = request.POST.get('city')
    location = request.POST.get('location')  # could be "lat,lng" or text
    description = request.POST.get('description')
    image_url = request.POST.get('image_url')
    audio_url = request.POST.get('audio_url')
    audio_transcript = request.POST.get('audio_transcript')
    image_caption = request.POST.get('image_caption')
    keywords = request.POST.getlist('keywords') if hasattr(request, 'POST') else None

    if not all([user_id, department, city, location, description]):
        return JsonResponse({'ok': False, 'error': 'missing_fields'}, status=400)

    report_id = fs_create_report(
        user_id=user_id,
        department=department,
        city=city,
        location=location,
        description=description,
        image_url=image_url,
        audio_url=audio_url,
        audio_transcript=audio_transcript,
        image_caption=image_caption,
        keywords=keywords or [],
    )
    return JsonResponse({'ok': True, 'report_id': report_id})

@require_POST
def api_increment_report_count(request):
    if not _require_admin(request):
        return HttpResponseForbidden('Auth required')
    user_id = request.POST.get('user_id')
    if not user_id:
        return JsonResponse({'ok': False, 'error': 'missing_user_id'}, status=400)
    try:
        fs_increment_reports(user_id)
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': 'failed_to_increment'}, status=500)

from google.genai import types
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
import os
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def api_generate_fix_suggestions(request):
    """
    Generate ways to fix the issue using Gemini (v1 API).
    Saves the result to Firestore on the same report document.
    """

    # Require staff (admin or department_head)
    user = request.session.get('admin_user') or {}
    if not (user and user.get('role') in ('admin', 'department_head')):
        return HttpResponseForbidden('Auth required')

    report_id = request.POST.get('report_id')
    image_caption = request.POST.get('image_caption') or ''
    user_description = request.POST.get('user_description') or ''

    if not report_id:
        return JsonResponse({'ok': False, 'error': 'missing_report_id'}, status=400)

    try:
        # --- API KEY RESOLUTION ---
        api_key = (
            os.environ.get('GOOGLE_GENAI_API_KEY') or
            os.environ.get('GEMINI_API_KEY') or
            getattr(settings, 'GOOGLE_GENAI_API_KEY', None) or
            getattr(settings, 'GEMINI_API_KEY', None)
        )

        if not api_key:
            logger.error('Gemini API key missing')
            return JsonResponse({'ok': False, 'error': 'missing_api_key'}, status=500)

        # --- NEW GEMINI CLIENT (v1) ---
        client = genai.Client(api_key=api_key)

        # --- PROMPT ---
        prompt = f"""
You are an expert advisor for Indian municipal and government agencies. Analyze the following civic issue and provide actionable solutions.

ISSUE DETAILS:
- Description: {user_description}
- Visual Context: {image_caption}

CONTEXT FOR SOLUTIONS:
- Indian government budget constraints (municipal budgets typically ₹500-5000 crores annually)
- Available resources: PWD, Municipal Corporation, District Administration, State Government schemes
- Implementation timeframe: Immediate (1-3 months), Short-term (3-12 months), Long-term (1-3 years)
- Funding sources: Municipal funds, State schemes, Central schemes (MGNREGA, Smart Cities, Swachh Bharat)

REQUIRED OUTPUT FORMAT:
Provide exactly 3-5 solutions in this structured format:

## SOLUTION [NUMBER]: [BRIEF TITLE]

**Steps:**
1. [Specific action step]
2. [Specific action step]
3. [Specific action step]

**Responsible Department:** [Primary department/authority]  
**Budget Estimate:** [Low: <₹1 lakh | Medium: ₹1-10 lakhs | High: >₹10 lakhs]  
**Timeline:** [Immediate/Short-term/Long-term]  
**Funding Source:** [Municipal/State scheme/Central scheme]

CONSTRAINTS:
- Cost-effective and locally implementable
- Consider monsoon and Indian weather
- Community participation where applicable
- Required approvals if any
- Sustainable & low-maintenance
"""

        logger.info('Calling Gemini (v1) for report_id=%s', report_id)

        # --- GEMINI CALL ---
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                top_p=0.8,
                max_output_tokens=2048,
            ),
        )

        text = (response.text or '').strip()

        if not text:
            logger.error('Gemini returned empty response for report_id=%s', report_id)
            return JsonResponse({'ok': False, 'error': 'empty_response'}, status=502)

        # --- SAVE TO FIRESTORE ---
        try:
            db.collection('reports').document(report_id).update({
                'ai_fix_suggestions': text,
                'ai_fix_generated_at': timezone.now(),
                'ai_prompt_version': 'v3_gemini_v1',
            })
            logger.info(
                'Saved ai_fix_suggestions for report_id=%s (len=%d)',
                report_id,
                len(text),
            )
        except Exception as save_err:
            logger.exception(
                'Failed saving ai_fix_suggestions for report_id=%s: %s',
                report_id,
                save_err,
            )
            # Still return the result

        return JsonResponse({'ok': True, 'suggestions': text})

    except Exception as e:
        logger.exception(
            'Gemini generation failed for report_id=%s: %s',
            report_id,
            e,
        )
        return JsonResponse({'ok': False, 'error': 'generation_failed'}, status=500)



def analytics_dashboard(request):
    """Main analytics dashboard view"""
    if not _require_staff(request):
        return redirect('login')
    
    try:
        start_report_caption_listener()
    except Exception:
        logger.exception("Failed ensuring report caption listener is running")
    
    ctx = {
        'current_user': request.session.get('admin_user') or {}
    }
    return render(request, 'analytics_dashboard.html', ctx)


@require_GET
def api_analytics_overview(request):
    """Get overview analytics for the dashboard"""
    if not _require_staff(request):
        return HttpResponseForbidden('Auth required')
    
    try:
        # Get user role and department for filtering
        role = _get_session_role(request)
        department = _get_session_department(request)
        # Read query params
        days = int(request.GET.get('days', '90'))  # default last 90 days for overview
        dept_filter = (request.GET.get('department') or '').strip()
        priority_filter = (request.GET.get('priority') or '').strip().lower()
        logger.info("[analytics_overview] params days=%s dept_filter='%s' priority_filter='%s' role=%s session_dept='%s'", days, dept_filter, priority_filter, role, department)
        
        # Fetch reports with department filtering
        reports_query = db.collection('reports').order_by('created_at', direction='DESCENDING')
        
        # Apply department filter for department heads
        if role == 'department_head' and department:
            # Note: Firestore requires index for compound queries
            # For now, we'll filter in memory after fetching
            pass
        
        reports_docs = list(reports_query.limit(1000).stream())
        reports_data = []
        
        for doc in reports_docs:
            data = _serialize_doc(doc)
            # Time filter (client provided)
            try:
                created_at = data.get('created_at')
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except Exception:
                created_at = None
            if days and created_at:
                created_at = _ensure_aware(created_at)
                if created_at < (timezone.now() - timedelta(days=days)):
                    continue
            # Apply department filtering for department heads
            if role == 'department_head' and department:
                if str(data.get('department', '')).strip().lower() != department.strip().lower():
                    continue
            # Apply explicit department filter from UI (overrides/augments)
            if dept_filter:
                if str(data.get('department', '')).strip().lower() != dept_filter.strip().lower():
                    continue
            # Apply priority filter if provided
            if priority_filter and str(data.get('priority', '')).strip().lower() != priority_filter:
                continue
            reports_data.append(data)
        
        # Fetch users data
        users_docs = list(db.collection('users').stream())
        users_data = [doc.to_dict() for doc in users_docs if doc.exists]
        
        # Calculate analytics
        overview = calculate_overview_metrics(reports_data, users_data)
        logger.info("[analytics_overview] results: reports=%d users=%d", len(reports_data), len(users_data))
        
        return JsonResponse({'ok': True, 'data': overview})
        
    except Exception as e:
        logger.exception("Failed to fetch overview analytics: %s", e)
        return JsonResponse({'ok': False, 'error': 'fetch_failed'}, status=500)


@require_GET
def api_analytics_trends(request):
    """Get trend analytics for charts"""
    if not _require_staff(request):
        return HttpResponseForbidden('Auth required')
    
    try:
        role = _get_session_role(request)
        department = _get_session_department(request)
        days = int(request.GET.get('days', '90'))
        dept_filter = (request.GET.get('department') or '').strip()
        priority_filter = (request.GET.get('priority') or '').strip().lower()
        logger.info("[analytics_trends] params days=%s dept_filter='%s' priority_filter='%s' role=%s session_dept='%s'", days, dept_filter, priority_filter, role, department)
        
        # Fetch recent reports (last N days)
        cutoff_date = timezone.now() - timedelta(days=days)
        reports_query = db.collection('reports').where('created_at', '>=', cutoff_date)
        
        reports_docs = list(reports_query.stream())
        reports_data = []
        
        for doc in reports_docs:
            data = _serialize_doc(doc)
            # Apply department filtering
            if role == 'department_head' and department:
                if str(data.get('department', '')).strip().lower() != department.strip().lower():
                    continue
            if dept_filter:
                if str(data.get('department', '')).strip().lower() != dept_filter.strip().lower():
                    continue
            if priority_filter and str(data.get('priority', '')).strip().lower() != priority_filter:
                continue
            reports_data.append(data)
        
        trends = calculate_trend_analytics(reports_data)
        logger.info("[analytics_trends] results: reports=%d", len(reports_data))
        
        return JsonResponse({'ok': True, 'data': trends})
        
    except Exception as e:
        logger.exception("Failed to fetch trend analytics: %s", e)
        return JsonResponse({'ok': False, 'error': 'fetch_failed'}, status=500)


@require_GET
def api_analytics_departments(request):
    """Get department-wise analytics"""
    if not _require_staff(request):
        return HttpResponseForbidden('Auth required')
    
    try:
        role = _get_session_role(request)
        user_department = _get_session_department(request)
        days = int(request.GET.get('days', '365'))
        dept_filter = (request.GET.get('department') or '').strip()
        priority_filter = (request.GET.get('priority') or '').strip().lower()
        logger.info("[analytics_departments] params days=%s dept_filter='%s' priority_filter='%s' role=%s session_dept='%s'", days, dept_filter, priority_filter, role, user_department)
        
        reports_docs = list(db.collection('reports').limit(1000).stream())
        reports_data = []
        
        for doc in reports_docs:
            data = _serialize_doc(doc)
            # Time filter
            try:
                created_at = data.get('created_at')
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                created_at = _ensure_aware(created_at)
            except Exception:
                created_at = timezone.now()
            if days and created_at:
                if created_at < (timezone.now() - timedelta(days=days)):
                    continue
            # Apply department filtering for department heads
            if role == 'department_head' and user_department:
                if str(data.get('department', '')).strip().lower() != user_department.strip().lower():
                    continue
            if dept_filter:
                if str(data.get('department', '')).strip().lower() != dept_filter.strip().lower():
                    continue
            if priority_filter and str(data.get('priority', '')).strip().lower() != priority_filter:
                continue
            reports_data.append(data)
        
        dept_analytics = calculate_department_analytics(reports_data)
        logger.info("[analytics_departments] results: departments=%d (from reports=%d)", len(dept_analytics.keys()), len(reports_data))
        
        return JsonResponse({'ok': True, 'data': dept_analytics})
        
    except Exception as e:
        logger.exception("Failed to fetch department analytics: %s", e)
        return JsonResponse({'ok': False, 'error': 'fetch_failed'}, status=500)


@require_GET
def api_analytics_response_times(request):
    """Get response time analytics"""
    if not _require_staff(request):
        return HttpResponseForbidden('Auth required')
    
    try:
        role = _get_session_role(request)
        department = _get_session_department(request)
        days = int(request.GET.get('days', '180'))
        dept_filter = (request.GET.get('department') or '').strip()
        priority_filter = (request.GET.get('priority') or '').strip().lower()
        logger.info("[analytics_response] params days=%s dept_filter='%s' priority_filter='%s' role=%s session_dept='%s'", days, dept_filter, priority_filter, role, department)
        
        reports_docs = list(db.collection('reports').limit(500).stream())
        reports_data = []
        
        for doc in reports_docs:
            data = _serialize_doc(doc)
            # Time filter
            try:
                created_at = data.get('created_at')
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except Exception:
                created_at = None
            if days and created_at and created_at < (datetime.now() - timedelta(days=days)):
                continue
            if role == 'department_head' and department:
                if str(data.get('department', '')).strip().lower() != department.strip().lower():
                    continue
            if dept_filter:
                if str(data.get('department', '')).strip().lower() != dept_filter.strip().lower():
                    continue
            if priority_filter and str(data.get('priority', '')).strip().lower() != priority_filter:
                continue
            reports_data.append(data)
        
        response_analytics = calculate_response_time_analytics(reports_data)
        logger.info("[analytics_response] results computed from reports=%d", len(reports_data))
        
        return JsonResponse({'ok': True, 'data': response_analytics})
        
    except Exception as e:
        logger.exception("Failed to fetch response time analytics: %s", e)
        return JsonResponse({'ok': False, 'error': 'fetch_failed'}, status=500)


@require_GET
def api_analytics_geographic(request):
    """Get geographic distribution analytics"""
    if not _require_staff(request):
        return HttpResponseForbidden('Auth required')
    
    try:
        role = _get_session_role(request)
        department = _get_session_department(request)
        days = int(request.GET.get('days', '365'))
        dept_filter = (request.GET.get('department') or '').strip()
        priority_filter = (request.GET.get('priority') or '').strip().lower()
        logger.info("[analytics_geo] params days=%s dept_filter='%s' priority_filter='%s' role=%s session_dept='%s'", days, dept_filter, priority_filter, role, department)
        
        reports_docs = list(db.collection('reports').limit(1000).stream())
        reports_data = []
        
        for doc in reports_docs:
            data = _serialize_doc(doc)
            # Time filter
            try:
                created_at = data.get('created_at')
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except Exception:
                created_at = None
            if days and created_at and created_at < (datetime.now() - timedelta(days=days)):
                continue
            if role == 'department_head' and department:
                if str(data.get('department', '')).strip().lower() != department.strip().lower():
                    continue
            if dept_filter:
                if str(data.get('department', '')).strip().lower() != dept_filter.strip().lower():
                    continue
            if priority_filter and str(data.get('priority', '')).strip().lower() != priority_filter:
                continue
            reports_data.append(data)
        
        geo_analytics = calculate_geographic_analytics(reports_data)
        logger.info("[analytics_geo] results: cities=%d (from reports=%d)", len(geo_analytics.keys()), len(reports_data))
        
        return JsonResponse({'ok': True, 'data': geo_analytics})
        
    except Exception as e:
        logger.exception("Failed to fetch geographic analytics: %s", e)
        return JsonResponse({'ok': False, 'error': 'fetch_failed'}, status=500)


# Helper functions for analytics calculations

def calculate_overview_metrics(reports_data: list[dict], users_data: list[dict]) -> dict:
    """Calculate overview metrics"""
    now = timezone.now()
    # Start of today in current timezone
    today = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Parse dates in reports
    for report in reports_data:
        if isinstance(report.get('created_at'), str):
            try:
                report['created_at'] = datetime.fromisoformat(report['created_at'].replace('Z', '+00:00'))
            except:
                report['created_at'] = now
        if isinstance(report.get('created_at'), datetime):
            report['created_at'] = _ensure_aware(report['created_at'])
    
    # Basic counts
    total_reports = len(reports_data)
    total_users = len(users_data)
    
    # Time-based filters
    reports_today = [r for r in reports_data if r.get('created_at', now) >= today]
    reports_this_week = [r for r in reports_data if r.get('created_at', now) >= week_ago]
    reports_this_month = [r for r in reports_data if r.get('created_at', now) >= month_ago]
    
    # Status distribution
    status_counts = Counter(r.get('status', 'pending') for r in reports_data)
    
    # Priority distribution
    priority_counts = Counter(r.get('priority', 'medium') for r in reports_data)
    
    # Department distribution
    dept_counts = Counter(r.get('department', 'Unknown') for r in reports_data)
    
    # City distribution
    city_counts = Counter(r.get('city', 'Unknown') for r in reports_data)
    
    # Resolution rate
    resolved_reports = len([r for r in reports_data if r.get('status') in ['resolved', 'completed']])
    resolution_rate = (resolved_reports / total_reports * 100) if total_reports > 0 else 0
    
    # Average response time (mock calculation)
    avg_response_hours = calculate_average_response_time(reports_data)
    
    return {
        'total_reports': total_reports,
        'total_users': total_users,
        'reports_today': len(reports_today),
        'reports_this_week': len(reports_this_week),
        'reports_this_month': len(reports_this_month),
        'resolution_rate': round(resolution_rate, 2),
        'avg_response_hours': round(avg_response_hours, 2),
        'status_distribution': dict(status_counts),
        'priority_distribution': dict(priority_counts),
        'department_distribution': dict(dept_counts),
        'city_distribution': dict(city_counts),
        'top_departments': dict(dept_counts.most_common(5)),
        'top_cities': dict(city_counts.most_common(5))
    }


def calculate_trend_analytics(reports_data: list[dict]) -> dict:
    """Calculate trend analytics for charts"""
    # Parse dates
    for report in reports_data:
        if isinstance(report.get('created_at'), str):
            try:
                report['created_at'] = datetime.fromisoformat(report['created_at'].replace('Z', '+00:00'))
            except:
                report['created_at'] = timezone.now()
        if isinstance(report.get('created_at'), datetime):
            report['created_at'] = _ensure_aware(report['created_at'])
    
    # Daily report trends (last 30 days)
    daily_counts = defaultdict(int)
    daily_resolved = defaultdict(int)
    
    for report in reports_data:
        date_key = report['created_at'].date().isoformat()
        daily_counts[date_key] += 1
        if report.get('status') in ['resolved', 'completed']:
            daily_resolved[date_key] += 1
    
    # Generate last 30 days
    daily_trends = []
    for i in range(29, -1, -1):
        date = (timezone.now() - timedelta(days=i)).date()
        date_key = date.isoformat()
        daily_trends.append({
            'date': date_key,
            'reports': daily_counts[date_key],
            'resolved': daily_resolved[date_key]
        })
    
    # Monthly trends (last 12 months)
    monthly_counts = defaultdict(int)
    monthly_resolved = defaultdict(int)
    
    for report in reports_data:
        month_key = report['created_at'].strftime('%Y-%m')
        monthly_counts[month_key] += 1
        if report.get('status') in ['resolved', 'completed']:
            monthly_resolved[month_key] += 1
    
    monthly_trends = []
    for i in range(11, -1, -1):
        date = timezone.now() - timedelta(days=i*30)
        month_key = date.strftime('%Y-%m')
        month_name = date.strftime('%b %Y')
        monthly_trends.append({
            'month': month_name,
            'month_key': month_key,
            'reports': monthly_counts[month_key],
            'resolved': monthly_resolved[month_key]
        })
    
    # Department trends
    dept_trends = defaultdict(lambda: defaultdict(int))
    for report in reports_data:
        dept = report.get('department', 'Unknown')
        week = report['created_at'].strftime('%Y-W%U')
        dept_trends[dept][week] += 1
    
    return {
        'daily_trends': daily_trends,
        'monthly_trends': monthly_trends,
        'department_weekly_trends': dict(dept_trends)
    }


def calculate_department_analytics(reports_data: list[dict]) -> dict:
    """Calculate department-wise analytics"""
    dept_data = defaultdict(lambda: {
        'total_reports': 0,
        'pending': 0,
        'in_progress': 0,
        'resolved': 0,
        'high_priority': 0,
        'medium_priority': 0,
        'low_priority': 0,
        'avg_response_time': 0,
        'cities': defaultdict(int)
    })
    
    for report in reports_data:
        dept = report.get('department', 'Unknown')
        status = report.get('status', 'pending')
        priority = report.get('priority', 'medium')
        city = report.get('city', 'Unknown')
        
        dept_data[dept]['total_reports'] += 1
        dept_data[dept]['cities'][city] += 1
        
        if status == 'pending':
            dept_data[dept]['pending'] += 1
        elif status == 'in_progress':
            dept_data[dept]['in_progress'] += 1
        elif status in ['resolved', 'completed']:
            dept_data[dept]['resolved'] += 1
        
        if priority == 'high':
            dept_data[dept]['high_priority'] += 1
        elif priority == 'medium':
            dept_data[dept]['medium_priority'] += 1
        elif priority == 'low':
            dept_data[dept]['low_priority'] += 1
    
    # Convert defaultdict to regular dict and calculate percentages
    result = {}
    for dept, data in dept_data.items():
        total = data['total_reports']
        if total > 0:
            result[dept] = {
                **data,
                'cities': dict(data['cities']),
                'resolution_rate': round(data['resolved'] / total * 100, 2),
                'pending_rate': round(data['pending'] / total * 100, 2)
            }
    
    return result


def calculate_response_time_analytics(reports_data: list[dict]) -> dict:
    """Calculate response time analytics"""
    response_times = []
    dept_response_times = defaultdict(list)
    priority_response_times = defaultdict(list)
    
    for report in reports_data:
        # Mock response time calculation (in real scenario, you'd have actual timestamps)
        created_at = report.get('created_at')
        status = report.get('status', 'pending')
        dept = report.get('department', 'Unknown')
        priority = report.get('priority', 'medium')
        
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except:
                created_at = timezone.now()
        if isinstance(created_at, datetime):
            created_at = _ensure_aware(created_at)
        
        # Mock response time based on status and priority
        if status in ['resolved', 'completed']:
            if priority == 'high':
                mock_response_hours = 24 + (hash(str(report)) % 48)  # 1-3 days
            elif priority == 'medium':
                mock_response_hours = 72 + (hash(str(report)) % 96)  # 3-7 days
            else:
                mock_response_hours = 168 + (hash(str(report)) % 168)  # 7-14 days
        else:
            # For pending/in-progress, calculate time since creation
            hours_since = (timezone.now() - created_at).total_seconds() / 3600
            mock_response_hours = hours_since
        
        response_times.append(mock_response_hours)
        dept_response_times[dept].append(mock_response_hours)
        priority_response_times[priority].append(mock_response_hours)
    
    # Calculate averages
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    
    dept_avg_response = {}
    for dept, times in dept_response_times.items():
        dept_avg_response[dept] = sum(times) / len(times) if times else 0
    
    priority_avg_response = {}
    for priority, times in priority_response_times.items():
        priority_avg_response[priority] = sum(times) / len(times) if times else 0
    
    return {
        'overall_avg_hours': round(avg_response_time, 2),
        'department_avg_hours': {k: round(v, 2) for k, v in dept_avg_response.items()},
        'priority_avg_hours': {k: round(v, 2) for k, v in priority_avg_response.items()},
        'response_time_distribution': {
            '< 24h': len([t for t in response_times if t < 24]),
            '1-3 days': len([t for t in response_times if 24 <= t < 72]),
            '3-7 days': len([t for t in response_times if 72 <= t < 168]),
            '> 1 week': len([t for t in response_times if t >= 168])
        }
    }


def calculate_geographic_analytics(reports_data: list[dict]) -> dict:
    """Calculate geographic distribution analytics"""
    city_data = defaultdict(lambda: {
        'total_reports': 0,
        'resolved': 0,
        'departments': defaultdict(int),
        'priorities': defaultdict(int),
        'coordinates': []
    })
    
    for report in reports_data:
        city = report.get('city', 'Unknown')
        dept = report.get('department', 'Unknown')
        priority = report.get('priority', 'medium')
        status = report.get('status', 'pending')
        
        city_data[city]['total_reports'] += 1
        city_data[city]['departments'][dept] += 1
        city_data[city]['priorities'][priority] += 1
        
        if status in ['resolved', 'completed']:
            city_data[city]['resolved'] += 1
        
        # Extract coordinates if available
        lat = report.get('lat')
        lng = report.get('lng')
        if lat and lng:
            city_data[city]['coordinates'].append({'lat': lat, 'lng': lng})
    
    # Convert to regular dict and add calculated fields
    result = {}
    for city, data in city_data.items():
        total = data['total_reports']
        result[city] = {
            'total_reports': total,
            'resolved': data['resolved'],
            'resolution_rate': round(data['resolved'] / total * 100, 2) if total > 0 else 0,
            'departments': dict(data['departments']),
            'priorities': dict(data['priorities']),
            'coordinates': data['coordinates']
        }
    
    return result


def calculate_average_response_time(reports_data: list[dict]) -> float:
    """Calculate average response time across all reports"""
    response_times = []
    
    for report in reports_data:
        created_at = report.get('created_at')
        status = report.get('status', 'pending')
        priority = report.get('priority', 'medium')
        
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except:
                created_at = timezone.now()
        if isinstance(created_at, datetime):
            created_at = _ensure_aware(created_at)
        
        # Mock response time calculation
        if status in ['resolved', 'completed']:
            if priority == 'high':
                mock_hours = 48 + (hash(str(report)) % 48)
            elif priority == 'medium':
                mock_hours = 96 + (hash(str(report)) % 72)
            else:
                mock_hours = 168 + (hash(str(report)) % 168)
            response_times.append(mock_hours)
        else:
            hours_since = (timezone.now() - created_at).total_seconds() / 3600
            response_times.append(hours_since)
    
    return sum(response_times) / len(response_times) if response_times else 0