from app.database import SessionLocal
from app.models.org import Tenant
from app.models.user import User

db = SessionLocal()
tenant = db.query(Tenant).filter(Tenant.name == "Rithesh").first()
if tenant:
    tenant.name = "Nexora Technologies Pvt. Ltd."
    print("Updated tenant name")

user = db.query(User).filter(User.full_name == "Nexora Technologies Pvt. Ltd.").first()
if user:
    user.full_name = "Rithesh"
    print("Updated user name")

db.commit()
print("Done swapping names in DB")
