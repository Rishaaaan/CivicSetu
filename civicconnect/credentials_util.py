import os
import glob
from typing import Optional

# Centralized resolver for Firebase service account JSON path.
# Order:
# 1) Explicit env var GOOGLE_APPLICATION_CREDENTIALS (if file exists)
# 2) Render Secret Files mount at /etc/secrets/<filename> (if exists)
# 3) Local repo path civicconnect/<filename> (if exists)
# 4) First match for *firebase-adminsdk-*.json under civicconnect/
# 5) Return fallback path (even if not existing) so caller can raise a clear error

DEFAULT_FILENAME = "civicconnect-2c5cb-1802f4750caa.json"
RENDER_SECRETS_DIR = "/etc/secrets"


def _first_existing(paths) -> Optional[str]:
    for p in paths:
        if p and os.path.isfile(p):
            return p
    return None


def get_service_account_path(base_dir: Optional[str] = None) -> str:
    """Resolve the path to the Firebase service account JSON.

    base_dir defaults to this file's directory's parent (the app root that contains civicconnect/).
    """
    if base_dir is None:
        # This file lives in civicconnect/, so parent dir is the app root
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 1) GOOGLE_APPLICATION_CREDENTIALS
    gac = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    # 2) Render Secret Files mount
    render_secret = os.path.join(RENDER_SECRETS_DIR, DEFAULT_FILENAME)

    # 3) Local repo path
    local_path = os.path.join(base_dir, "civicconnect", DEFAULT_FILENAME)

    # 4) Glob for any admin SDK file under civicconnect/
    globbed = []
    civic_dir = os.path.join(base_dir, "civicconnect")
    try:
        globbed = glob.glob(os.path.join(civic_dir, "*firebase-adminsdk-*.json"))
    except Exception:
        globbed = []

    candidate = _first_existing([gac, render_secret, local_path] + globbed)

    # 5) Return the best candidate, or a sensible fallback even if missing.
    if candidate:
        return candidate

    # Fall back to local path so callers can show a consistent error
    return local_path
