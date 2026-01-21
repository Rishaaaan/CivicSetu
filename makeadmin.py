import firebase_admin
from firebase_admin import credentials, auth

# Use your service account JSON file (the same one you use in Django)
cred = credentials.Certificate("civicconnect\civicconnect-2c5cb-1802f4750caa.json")
firebase_admin.initialize_app(cred)

# Now set the admin claim
auth.set_custom_user_claims("RdOcoUdWRzLe9S2Oqw4AKZdS0kQ2", {"role": "admin"})

print("✅ Admin role set successfully!")
