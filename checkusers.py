import firebase_admin
from firebase_admin import credentials, auth
from civicconnect.credentials_util import get_service_account_path

# Initialize Firebase Admin SDK (replace with your credentials path)
cred = credentials.Certificate(get_service_account_path())
firebase_admin.initialize_app(cred)

def list_all_users():
    page = auth.list_users()
    while page:
        for user in page.users:
            print("UID:", user.uid)
            print("Email:", user.email)
            print("Role:", user.name)
            print("Custom Claims:", user.custom_claims)  # <-- roles like admin should appear here
            print("Disabled:", user.disabled)
            print("-" * 50)
        page = page.get_next_page()

if __name__ == "__main__":
    list_all_users()
