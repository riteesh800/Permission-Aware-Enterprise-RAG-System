from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_admin_user_readonly
from app.models.audit import AuditLog
from app.models.user import User

router = APIRouter(prefix="/api/admin/audit-logs", tags=["admin-audit"])


@router.get("")
def list_logs(admin=Depends(get_admin_user_readonly), db: Session = Depends(get_db)):
    admin_tenant = admin.tenant_id or admin.id
    logs_with_users = (
        db.query(AuditLog, User)
        .outerjoin(User, AuditLog.actor_user_id == User.id)
        .filter(AuditLog.tenant_id == admin_tenant)
        .order_by(AuditLog.timestamp.desc())
        .limit(200)
        .all()
    )
    
    result = []
    for log, user in logs_with_users:
        req_id = log.request_id
        if req_id == "employee" and user and user.full_name:
            req_id = user.full_name
            
        result.append({
            "id": log.id,
            "timestamp": (log.timestamp.isoformat() + ("Z" if not log.timestamp.isoformat().endswith("Z") and "+" not in log.timestamp.isoformat() else "")) if log.timestamp else None,
            "actor_user_id": log.actor_user_id,
            "actor_name": user.full_name if user else log.actor_user_id,
            "action": log.action,
            "status": log.status,
            "request_id": req_id,
            "document_id": log.document_id,
            "result_count": log.result_count,
            "denied_result_count": log.denied_result_count,
            "target": log.detail,
        })
    return result

