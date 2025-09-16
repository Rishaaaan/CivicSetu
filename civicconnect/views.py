from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import firebase_admin
from firebase_admin import auth as fb_auth
from .firebase import db, create_user as fs_create_user, create_report as fs_create_report
from .firebase import increment_reports as fs_increment_reports
from google.cloud.firestore import Client
from datetime import datetime


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
    return render(request, 'register_user.html')


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
    except Exception:
        pass

    if role != 'admin':
        return JsonResponse({'ok': False, 'error': 'not_admin'}, status=403)

    # Set session
    request.session['admin_user'] = {
        'uid': uid,
        'email': email,
        'name': decoded.get('name'),
    }
    return JsonResponse({'ok': True})



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
    return render(request, 'civic_admin_dashboard_DarkTheme.html')


def _require_admin(request):
    if not request.session.get('admin_user'):
        return False
    return True


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
    if not _require_admin(request):
        return HttpResponseForbidden('Auth required')
    try:
        # Recent first
        q = db.collection('reports').order_by('created_at', direction='DESCENDING').limit(200)
        raw_docs = list(q.stream())
        items = [_serialize_doc(d) for d in raw_docs]
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
