import sys
sys.path.insert(0, ".")
from app.database import SessionLocal
from app.auth.service import AuthenticationService
from app.models.user import User

db = SessionLocal()
user = db.query(User).filter(User.email=="aaravmehta123@gmail.com").first()
auth_service = AuthenticationService(db)
auth_user = auth_service.to_auth_user(user)
print("Role names:", auth_user.role_names)
