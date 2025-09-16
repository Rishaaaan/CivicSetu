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


def display_all_reports(db):
    reports_ref = db.collection('reports')
    reports = list(reports_ref.stream())
    if not reports:
        print("No reports found.")
        return

    print(f"Total reports found: {len(reports)}\n")
    for report in reports:
        data = report.to_dict()
        print(f"Report ID: {data.get('report_id', report.id)}")
        print(f"User ID: {data.get('user_id')}")
        print(f"Department: {data.get('department')}")
        print(f"City: {data.get('city')}")
        print(f"Location: {data.get('location')}")
        print(f"Status: {data.get('status')}")
        print(f"Image URL: {data.get('image_url')}")
        print(f"Image Caption: {data.get('image_caption')}")
        print(f"Audio URL: {data.get('audio_url')}")
        print(f"Audio Transcript: {data.get('audio_transcript')}")
        print(f"Keywords: {data.get('keywords')}")
        print(f"User Description: {data.get('user_description')}")
        print(f"Created At: {data.get('created_at')}")
        print(f"Title: {data.get('title')}")
        print(f"Priority: {data.get('priority')}")
        print(f"Type: {data.get('type')}")
        print("-" * 40)


def main():
    db = init_firestore()
    display_all_reports(db)


if __name__ == '__main__':
    main()
