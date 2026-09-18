from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.auth.service import AuthenticationService
from app.config import get_settings
from app.database import get_db
from app.deps import get_admin_user, get_admin_user_readonly
from app.models.audit import AuditLog
from app.models.document import Document
from app.models.enums import IngestionStatus, AppRole
from app.models.org import Department, Group, Role
from app.models.user import User
from app.schemas import CreateUserRequest, DeleteUserRequest, PatchUserRequest, ResetPasswordRequest, UserPublic, CreateDepartmentRequest, VerifyDeleteRequest
from app.users.service import UserService

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _public(user: User, db: Session) -> dict:
    auth = AuthenticationService(db).to_auth_user(user)
    return UserPublic(
        id=auth.id,
        unique_identifier=auth.unique_identifier,
        email=auth.email,
        full_name=auth.full_name,
        app_role=auth.app_role,
        department_id=auth.department_id,
        is_active=auth.is_active,
        must_change_password=auth.must_change_password,
        role_names=auth.role_names,
        group_names=auth.group_names,
        role_ids=auth.role_ids,
        group_ids=auth.group_ids,
    ).model_dump()


@router.get("/dashboard")
def dashboard(admin=Depends(get_admin_user_readonly), db: Session = Depends(get_db)):
    admin_tenant = admin.tenant_id or admin.id
    users = db.query(User).filter(User.tenant_id == admin_tenant).all()
    docs = db.query(Document).filter(Document.tenant_id == admin_tenant).all()
    failed = [d for d in docs if d.ingestion_status == IngestionStatus.FAILED.value]
    
    events_query = (
        db.query(AuditLog, User)
        .join(User, AuditLog.actor_user_id == User.id)
        .filter(
            AuditLog.tenant_id == admin_tenant,
            AuditLog.action == "change_password",
            User.app_role == AppRole.EMPLOYEE.value
        )
        .order_by(AuditLog.timestamp.desc())
        .limit(10)
        .all()
    )
    
    events_data = []
    for event, user in events_query:
        ts = event.timestamp.isoformat() if event.timestamp else None
        if ts and not ts.endswith("Z") and "+" not in ts:
            ts += "Z"
        events_data.append({
            "id": event.id,
            "timestamp": ts,
            "action": event.action,
            "name": user.full_name
        })

    return {
        "total_users": len(users),
        "active_users": sum(1 for u in users if u.is_active),
        "documents": len(docs),
        "failed_ingestions": len(failed),
        "recent_security_events": events_data,
    }


@router.get("/org")
def org(admin=Depends(get_admin_user_readonly), db: Session = Depends(get_db)):
    admin_tenant = admin.tenant_id or admin.id
    return {
        "departments": [{"id": d.id, "name": d.name, "description": d.description} for d in db.query(Department).filter(Department.tenant_id == admin_tenant).all()],
        "roles": [{"id": r.id, "name": r.name, "description": r.description} for r in db.query(Role).filter(Role.tenant_id == admin_tenant).all()],
        "groups": [{"id": g.id, "name": g.name, "description": g.description} for g in db.query(Group).filter(Group.tenant_id == admin_tenant).all()],
    }

@router.post("/org/departments")
def create_department(
    payload: CreateDepartmentRequest,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    admin_tenant = admin.tenant_id or admin.id
    import uuid
    new_dept = Department(
        id=str(uuid.uuid4()),
        tenant_id=admin_tenant,
        name=payload.name,
        description=payload.description
    )
    db.add(new_dept)
    db.commit()
    db.refresh(new_dept)
    return {"id": new_dept.id, "name": new_dept.name, "description": new_dept.description}


@router.post("/users")
def create_user(
    payload: CreateUserRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    admin_tenant = admin.tenant_id or admin.id
    user = UserService(db).create_user(
        email=payload.email,
        full_name=payload.full_name,
        password=payload.password,
        department_id=payload.department_id,
        app_role=payload.app_role,
        unique_identifier=payload.unique_identifier,
        must_change_password=payload.must_change_password,
        tenant_id=admin_tenant,
    )
    AuditService(db).record(
        actor_user_id=admin.id,
        tenant_id=admin_tenant,
        action="create_user",
        request_id=request.headers.get("X-Request-ID", "admin"),
        status="SUCCESS",
        secret=get_settings().session_secret,
        detail=user.full_name,
    )
    return _public(user, db)


@router.get("/users")
def list_users(admin=Depends(get_admin_user_readonly), db: Session = Depends(get_db)):
    admin_tenant = admin.tenant_id or admin.id
    return [
        _public(u, db)
        for u in db.query(User)
        .filter(User.tenant_id == admin_tenant)
        .order_by(User.created_at.desc())
        .all()
    ]


@router.get("/users/{user_id}")
def get_user(user_id: str, admin=Depends(get_admin_user_readonly), db: Session = Depends(get_db)):
    admin_tenant = admin.tenant_id or admin.id
    user = db.get(User, user_id)
    if user is None or user.tenant_id != admin_tenant:
        raise HTTPException(status_code=404, detail="Not found")
    data = _public(user, db)
    data["access_summary"] = UserService(db).access_summary(user)
    return data


@router.patch("/users/{user_id}")
def patch_user(
    user_id: str,
    payload: PatchUserRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    admin_tenant = admin.tenant_id or admin.id
    user = db.get(User, user_id)
    if user is None or user.tenant_id != admin_tenant:
        raise HTTPException(status_code=404, detail="Not found")
    user = UserService(db).patch_user(user, payload.model_dump(exclude_unset=True))
    AuditService(db).record(
        actor_user_id=admin.id,
        tenant_id=admin_tenant,
        action="patch_user",
        request_id=request.headers.get("X-Request-ID", "admin"),
        status="SUCCESS",
        secret=get_settings().session_secret,
        detail=user.full_name,
    )
    return _public(user, db)


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: str,
    payload: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    admin_tenant = admin.tenant_id or admin.id
    user = db.get(User, user_id)
    if user is None or user.tenant_id != admin_tenant:
        raise HTTPException(status_code=404, detail="Not found")
    AuthenticationService(db).reset_password(user, payload.password, payload.must_change_password)
    AuditService(db).record(
        actor_user_id=admin.id,
        tenant_id=admin_tenant,
        action="reset_password",
        request_id=request.headers.get("X-Request-ID", "admin"),
        status="SUCCESS",
        secret=get_settings().session_secret,
        detail=user.full_name,
    )
    return {"ok": True}


@router.post("/users/{user_id}/verify-delete")
def verify_delete_user(
    user_id: str,
    payload: VerifyDeleteRequest,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    if user_id != admin.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if not payload.password and not payload.otp:
        raise HTTPException(status_code=400, detail="Must provide password or otp")

    if payload.password:
        from app.security.crypto import verify_password
        user = db.get(User, admin.id)
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=400, detail="Invalid password")
    elif payload.otp:
        from app.models.otp import EmailOtp
        from datetime import UTC, datetime
        from app.security.crypto import hash_token
        
        email = admin.email.lower().strip()
        otp_record = (
            db.query(EmailOtp)
            .filter(
                EmailOtp.email == email,
                EmailOtp.purpose == "account_deletion",
                EmailOtp.is_used.is_(False),
            )
            .order_by(EmailOtp.created_at.desc())
            .first()
        )
        if not otp_record:
            raise HTTPException(status_code=400, detail="No verification code was requested")
            
        exp = otp_record.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        if exp < datetime.now(UTC):
            raise HTTPException(status_code=400, detail="Verification code expired")
            
        if otp_record.attempts >= 5:
            otp_record.is_used = True
            db.commit()
            raise HTTPException(status_code=400, detail="Too many invalid attempts")
            
        if otp_record.otp_hash != hash_token(payload.otp.strip()):
            otp_record.attempts += 1
            db.commit()
            raise HTTPException(status_code=400, detail="Invalid verification code")
            
        otp_record.is_used = True
        db.commit()

    import secrets
    from datetime import timedelta, datetime, UTC
    from jose import jwt
    from app.config import get_settings
    now = datetime.now(UTC)
    settings = get_settings()
    token = jwt.encode({
        "sub": admin.id,
        "type": "delete_verification",
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "jti": secrets.token_urlsafe(16),
    }, settings.jwt_secret, algorithm="HS256")
    
    return {"ok": True, "token": token}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    request: Request,
    payload: DeleteUserRequest | None = None,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    admin_tenant = admin.tenant_id or admin.id
    user = db.get(User, user_id)
    if user is None or user.tenant_id != admin_tenant:
        raise HTTPException(status_code=404, detail="Not found")

    if user_id == admin.id:
        if not payload or not payload.token:
            raise HTTPException(status_code=400, detail="Missing deletion verification token")
        
        from jose import jwt, JWTError
        settings = get_settings()
        try:
            decoded = jwt.decode(payload.token, settings.jwt_secret, algorithms=["HS256"])
            if decoded.get("type") != "delete_verification" or decoded.get("sub") != admin.id:
                raise HTTPException(status_code=400, detail="Invalid verification token")
        except JWTError:
            raise HTTPException(status_code=400, detail="Invalid or expired verification token")

        from app.ingestion.service import IngestionService
        docs = db.query(Document).filter(Document.tenant_id == admin_tenant).all()
        ingestion_svc = IngestionService(db)
        for doc in docs:
            ingestion_svc.delete_document(doc)
            
        db.query(AuditLog).filter(AuditLog.tenant_id == admin_tenant).delete(synchronize_session=False)
        
        users_to_delete = db.query(User).filter(User.tenant_id == admin_tenant).all()
        for u in users_to_delete:
            db.delete(u)
            
        db.query(Department).filter(Department.tenant_id == admin_tenant).delete(synchronize_session=False)
        db.query(Role).filter(Role.tenant_id == admin_tenant).delete(synchronize_session=False)
        db.query(Group).filter(Group.tenant_id == admin_tenant).delete(synchronize_session=False)
        
        from app.models.org import Tenant
        tenant = db.get(Tenant, admin_tenant)
        if tenant:
            db.delete(tenant)
            
        db.commit()
    else:
        db.query(Document).filter(Document.owner_user_id == user_id).update(
            {"owner_user_id": None}, synchronize_session="fetch"
        )
        db.delete(user)
        db.commit()

        AuditService(db).record(
            actor_user_id=admin.id,
            tenant_id=admin_tenant,
            action="delete_user",
            request_id=request.headers.get("X-Request-ID", "admin"),
            status="SUCCESS",
            secret=get_settings().session_secret,
            detail=user.full_name,
        )
    return {"ok": True}

