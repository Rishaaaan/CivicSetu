import firebase_admin
from firebase_admin import credentials, firestore
import uuid
from datetime import datetime

# Initialize Firebase only once
cred = credentials.Certificate("civicconnect/civicconnect-2c5cb-1802f4750caa.json")
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(cred)

db = firestore.client()

# --------------------------
# Firestore Utility Functions
# --------------------------

def create_user(name, email, role="citizen", department=None, city="Unknown", auth_uid=None):
    """Create a new user (citizen or admin)."""
    user_id = str(uuid.uuid4())
    user_ref = db.collection("users").document(user_id)
    user_ref.set({
        "user_id": user_id,
        "auth_uid": auth_uid,
        "name": name,
        "email": email,
        "role": role,  # "citizen" or "admin"
        "department": department,
        "city": city,
        "reports_count": 0,
        "created_at": datetime.now()
    })
    print(f"✅ User created: {user_id}")
    return user_id


def create_report(user_id, department, city, location, description,
                  image_url=None, audio_url=None, audio_transcript=None,
                  image_caption=None, keywords=None):
    """Create a new report linked to a user."""
    report_id = str(uuid.uuid4())
    report_ref = db.collection("reports").document(report_id)
    report_ref.set({
        "report_id": report_id,
        "user_id": user_id,
        "department": department,
        "city": city,
        "location": location,   # string OR firestore.GeoPoint
        "status": "pending",
        "image_url": image_url,
        "image_caption": image_caption,
        "audio_url": audio_url,
        "audio_transcript": audio_transcript,
        "keywords": keywords if keywords else [],
        "user_description": description,
        "created_at": datetime.now()
    })

    # Increment reports_count for user
    increment_reports(user_id)

    print(f"✅ Report created: {report_id}")
    return report_id


def increment_reports(user_id):
    """Increment report count for leaderboard."""
    user_ref = db.collection("users").document(user_id)
    user_ref.update({
        "reports_count": firestore.Increment(1)
    })
