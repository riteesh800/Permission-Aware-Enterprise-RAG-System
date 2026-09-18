from app.database import SessionLocal
from app.models.audit import AuditLog

db = SessionLocal()
log = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).first()
if log:
    print("DB timestamp:", repr(log.timestamp))
    print("isoformat:", log.timestamp.isoformat())
else:
    print("No logs")
