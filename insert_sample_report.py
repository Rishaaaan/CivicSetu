import os
import sys
import glob
from datetime import datetime

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore


def find_service_account_json(base_dir: str) -> str:
    candidates = glob.glob(os.path.join(base_dir, 'civicconnect', '*firebase-adminsdk-*.json'))
    if candidates:
        return candidates[0]
    return os.path.join(base_dir, 'civicconnect', 'civicconnect-2c5cb-firebase-adminsdk-fbsvc-8f12e03b0f.json')


def init_firestore():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sa_path = find_service_account_json(base_dir)
    if not os.path.exists(sa_path):
        print(f"Service account JSON not found: {sa_path}")
        sys.exit(1)
    cred = credentials.Certificate(sa_path)
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(cred)
    return firestore.client()


def ensure_test_user(db) -> str:
    """Find or create a test citizen user and return user_id."""
    email = 'citizen.sample@civicsetu.local'
    docs = list(db.collection('users').where('email', '==', email).limit(1).stream())
    if docs:
        return docs[0].id
    doc_ref = db.collection('users').document()
    doc_ref.set({
        'user_id': doc_ref.id,
        'auth_uid': None,
        'name': 'Sample Citizen',
        'email': email,
        'role': 'citizen',
        'department': None,
        'city': 'Delhi',
        'reports_count': 0,
        'created_at': datetime.now(),
    })
    return doc_ref.id


def insert_sample_report(db):
    user_id = ensure_test_user(db)

    # Example report data (adjust as needed)
    data = {
        'report_id': None,  # will be set to doc id
        'user_id': user_id,
        'department': 'Electrical',
        'city': 'Delhi',
        # You can also store a string "lat,lng" or a Firestore GeoPoint
        'location': '28.8,77.3522',
        'status': 'pending',
        'image_url': 'https://imgs.search.brave.com/wAKDUQ9tYKe9SHalu4ScU1-tQZJGl2ZrLezW4_e-Ksc/rs:fit:500:0:1:0/g:ce/aHR0cHM6Ly90My5m/dGNkbi5uZXQvanBn/LzAyLzc2LzA2Lzcw/LzM2MF9GXzI3NjA2/NzA2OV9RVXlvUm1T/T2tlWG1TOHMwWEJ4/N3RNdHFudm40d09Q/Qy5qcGc',
        'image_caption': 'Broken water pipe ',
        'audio_url': None,
        'audio_transcript': None,
        'keywords': ['road', 'cracks'],
        'user_description': 'Broken and damaged road with large cracks.',
        'created_at': datetime.now(),
        # Optional custom fields often used by UI
        'title': 'Broken and damaged road',
        'priority': 'high',
        'type': 'road'
    }

    doc_ref = db.collection('reports').document()
    data['report_id'] = doc_ref.id
    doc_ref.set(data)

    # Increment the user's reports_count
    db.collection('users').document(user_id).update({
        'reports_count': firestore.Increment(1)
    })

    print('Inserted sample report:')
    print(f'  user_id: {user_id}')
    print(f'  report_id: {doc_ref.id}')


def main():
    db = init_firestore()
    insert_sample_report(db)


if __name__ == '__main__':
    main()

