from app.database import SessionLocal
from app.models.org import Tenant

db = SessionLocal()
tenant = db.query(Tenant).first()
if tenant:
    print("Tenant name:", repr(tenant.name))
else:
    print("No tenant found")
