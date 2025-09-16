import os
import sys
import getpass
import glob
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, auth, firestore


def find_service_account_json(base_dir: str) -> str:
    """Try to locate the Firebase service account JSON inside civicconnect/ directory."""
    candidates = glob.glob(os.path.join(base_dir, 'civicconnect', '*firebase-adminsdk-*.json'))
    if candidates:
        return candidates[0]
    # Fallback to a known filename
    fallback = os.path.join(base_dir, 'civicconnect', 'civicconnect-2c5cb-firebase-adminsdk-fbsvc-8f12e03b0f.json')
    return fallback


def init_firebase():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sa_path = find_service_account_json(base_dir)
    if not os.path.exists(sa_path):
        print(f"ERROR: Service account file not found at: {sa_path}")
        sys.exit(1)

    cred = credentials.Certificate(sa_path)
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(cred)  # ✅ no name param
    return firestore.client()


def create_firestore_user(db, name: str, email: str, auth_uid: str, department: str = None, city: str = 'Unknown') -> str:
    """Create Firestore user profile with admin role."""
    doc_ref = db.collection('users').document()
    doc_ref.set({
        'user_id': doc_ref.id,
        'auth_uid': auth_uid,
        'name': name,
        'email': email,
        'role': 'admin',
        'department': department,
        'city': city or 'Unknown',
        'reports_count': 0,
        'created_at': datetime.now()
    })
    return doc_ref.id


def main():
    print('=== CivicSetu: Create First Admin User ===')
    name = input('Full Name: ').strip()
    email = input('Email: ').strip()
    while True:
        password = getpass.getpass('Password (input hidden): ').strip()
        password2 = getpass.getpass('Confirm Password: ').strip()
        if password and password == password2:
            break
        print('Passwords do not match or empty. Try again.')
    department = input('Department (optional, e.g., Roads): ').strip() or None
    city = input('City (e.g., Delhi): ').strip() or 'Unknown'

    # Init Firebase
    db = init_firebase()

        # Create Firebase Auth user
    try:
        try:
            existing = auth.get_user_by_email(email)
            print(f"A Firebase Auth user with email {email} already exists (uid={existing.uid}).")
            uid = existing.uid
        except auth.UserNotFoundError:
            user_record = auth.create_user(
                email=email,
                password=password,
                display_name=name,
                email_verified=False,
                disabled=False,
            )
            uid = user_record.uid
            print(f"✓ Firebase Auth user created. uid={uid}")

        # ✅ Set admin role claim
        auth.set_custom_user_claims(uid, {"role": "admin"})
        print("✓ Custom claim 'role=admin' set for this user.")

    except Exception as e:
        print(f"ERROR creating Firebase Auth user: {e}")
        sys.exit(1)


    # Create Firestore user profile (role=admin)
    try:
        user_id = create_firestore_user(db, name=name, email=email, auth_uid=uid, department=department, city=city)
        print(f"✓ Firestore admin profile created. user_id={user_id}")
    except Exception as e:
        print(f"ERROR creating Firestore user document: {e}")
        sys.exit(1)

    print('\nAll done! You can now login at /login with the created admin credentials.')


if __name__ == '__main__':
    main()
