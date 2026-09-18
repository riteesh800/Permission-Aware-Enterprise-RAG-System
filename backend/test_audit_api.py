import urllib.request
import json
import sqlite3
from app.database import SessionLocal
from app.models.user import User

db = SessionLocal()
admin = db.query(User).filter_by(email="riteeritee251@gmail.com").first()
if not admin:
    print("Admin not found")
    exit()

from app.security.crypto import create_access_token
from app.config import get_settings
settings = get_settings()
token = create_access_token(settings, admin.id, admin.app_role, admin.permission_version)

req = urllib.request.Request("http://127.0.0.1:8000/api/admin/dashboard")
req.add_header("Cookie", f"access_token={token}")
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        print(json.dumps(data, indent=2))
except Exception as e:
    print(e)
