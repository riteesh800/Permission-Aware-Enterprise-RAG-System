from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

import secrets
from datetime import UTC, datetime, timedelta

from app.audit.service import AuditService
from app.auth.service import (
    AuthenticationService,
    require_csrf,
)
from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models.enums import AppRole, AuditStatus
from app.models.otp import EmailOtp
from app.models.user import User
from app.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    SendOtpRequest,
    VerifyAdminRegistrationRequest,
    ForgotPasswordResetRequest,
    VerifyOtpRequest,
    UserPublic,
)
from app.security.crypto import hash_password, hash_token, password_meets_policy
from app.security.ratelimit import rate_limit_login
from app.services.email import EmailService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register-admin/send-otp")
def send_admin_otp(payload: SendOtpRequest, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    # Prevent spamming OTP requests within 60 seconds
    one_min_ago = datetime.now(UTC) - timedelta(seconds=60)
    recent = (
        db.query(EmailOtp)
        .filter(
            EmailOtp.email == email,
            EmailOtp.is_used.is_(False),
            EmailOtp.created_at >= one_min_ago,
        )
        .first()
    )
    if recent:
        raise HTTPException(status_code=429, detail="Please wait 60 seconds before requesting another code")

    # Invalidate old unused OTPs for this email
    db.query(EmailOtp).filter(
        EmailOtp.email == email,
        EmailOtp.is_used.is_(False),
    ).update({"is_used": True})

    otp_code = f"{secrets.randbelow(900000) + 100000:06d}"
    otp_record = EmailOtp(
        email=email,
        otp_hash=hash_token(otp_code),
        purpose="admin_registration",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db.add(otp_record)
    db.commit()

    email_service = EmailService(get_settings())
    try:
        email_service.send_otp_email(email, otp_code)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {exc}") from exc

    return {"ok": True, "message": "Verification code sent to your email"}


@router.post("/delete-account/send-otp")
def delete_account_send_otp(user=Depends(get_current_user), db: Session = Depends(get_db)):
    if user.app_role != AppRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Forbidden")

    email = user.email.lower().strip()

    one_min_ago = datetime.now(UTC) - timedelta(seconds=60)
    recent = (
        db.query(EmailOtp)
        .filter(
            EmailOtp.email == email,
            EmailOtp.is_used.is_(False),
            EmailOtp.created_at >= one_min_ago,
        )
        .first()
    )
    if recent:
        raise HTTPException(status_code=429, detail="Please wait 60 seconds before requesting another code")

    db.query(EmailOtp).filter(
        EmailOtp.email == email,
        EmailOtp.is_used.is_(False),
    ).update({"is_used": True})

    otp_code = f"{secrets.randbelow(900000) + 100000:06d}"
    otp_record = EmailOtp(
        email=email,
        otp_hash=hash_token(otp_code),
        purpose="account_deletion",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db.add(otp_record)
    db.commit()

    email_service = EmailService(get_settings())
    try:
        email_service.send_otp_email(email, otp_code)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {exc}") from exc

    return {"ok": True, "message": "Deletion verification code sent to your email"}


@router.post("/register-admin/verify")
def verify_admin_registration(
    payload: VerifyAdminRegistrationRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    email = payload.email.lower().strip()
    full_name = payload.full_name.strip()

    if not password_meets_policy(payload.password):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters and contain a mix of letters and numbers",
        )

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    otp_record = (
        db.query(EmailOtp)
        .filter(
            EmailOtp.email == email,
            EmailOtp.purpose == "admin_registration",
            EmailOtp.is_used.is_(False),
        )
        .order_by(EmailOtp.created_at.desc())
        .first()
    )

    if not otp_record:
        raise HTTPException(status_code=400, detail="No verification code was requested for this email")

    # Check expiration (ensure comparison is timezone-aware)
    exp = otp_record.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    if exp < datetime.now(UTC):
        raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new one.")

    if otp_record.attempts >= 5:
        otp_record.is_used = True
        db.commit()
        raise HTTPException(status_code=400, detail="Too many invalid attempts. Please request a new verification code.")

    if otp_record.otp_hash != hash_token(payload.otp.strip()):
        otp_record.attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid verification code")

    # Mark OTP as successfully used
    otp_record.is_used = True

    # If the default demo admin exists, remove it so the newly registered admin is the sole administrator
    demo_admin = db.query(User).filter(User.email == "admin@acme.local").first()
    if demo_admin:
        db.delete(demo_admin)
        db.flush()

    # Generate next unique identifier for the Admin
    settings = get_settings()
    prefix = settings.company_prefix
    total_admins = db.query(User).filter(User.app_role == AppRole.ADMIN.value).count()
    ident = f"{prefix}-ADMIN-{(total_admins + 1):04d}"
    while db.query(User).filter(User.unique_identifier == ident).first():
        total_admins += 1
        ident = f"{prefix}-ADMIN-{(total_admins + 1):04d}"


    import uuid
    admin_id = str(uuid.uuid4())
    
    from app.models.org import Tenant
    new_tenant = Tenant(id=admin_id, name=payload.company_name.strip())
    db.add(new_tenant)
    db.flush()

    new_admin = User(
        id=admin_id,
        unique_identifier=ident,
        email=email,
        full_name=full_name,
        password_hash=hash_password(payload.password),
        app_role=AppRole.ADMIN.value,
        tenant_id=admin_id,
        is_active=True,
        must_change_password=False,
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    auth = AuthenticationService(db, settings)
    auth.issue_session(response, new_admin)
    auth_user = auth.to_auth_user(new_admin)

    AuditService(db).record(
        actor_user_id=new_admin.id,
        tenant_id=new_admin.tenant_id,
        action="register_admin",
        request_id=request.headers.get("X-Request-ID", "register"),
        status=AuditStatus.SUCCESS.value,
        ip=request.client.host if request.client else None,
        secret=settings.session_secret,
    )


    return {
        "user": UserPublic(
            id=auth_user.id,
            unique_identifier=auth_user.unique_identifier,
            email=auth_user.email,
            full_name=auth_user.full_name,
            app_role=auth_user.app_role,
            department_id=auth_user.department_id,
            is_active=auth_user.is_active,
            must_change_password=auth_user.must_change_password,
            company_name=auth_user.company_name,
            role_names=auth_user.role_names,
            group_names=auth_user.group_names,
        ).model_dump()
    }



@router.post("/forgot-password/send-otp")
def forgot_password_send_otp(payload: SendOtpRequest, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()

    existing = db.query(User).filter(User.email == email).first()
    if not existing or existing.app_role != AppRole.ADMIN.value:
        # Prevent user enumeration by acting as if it succeeded
        return {"ok": True, "message": "If an admin account exists, a code was sent"}

    # Prevent spamming OTP requests within 60 seconds
    one_min_ago = datetime.now(UTC) - timedelta(seconds=60)
    recent = (
        db.query(EmailOtp)
        .filter(
            EmailOtp.email == email,
            EmailOtp.is_used.is_(False),
            EmailOtp.created_at >= one_min_ago,
        )
        .first()
    )
    if recent:
        raise HTTPException(status_code=429, detail="Please wait 60 seconds before requesting another code")

    # Invalidate old unused OTPs for this email
    db.query(EmailOtp).filter(
        EmailOtp.email == email,
        EmailOtp.is_used.is_(False),
    ).update({"is_used": True})

    otp_code = f"{secrets.randbelow(900000) + 100000:06d}"
    otp_record = EmailOtp(
        email=email,
        otp_hash=hash_token(otp_code),
        purpose="password_reset",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db.add(otp_record)
    db.commit()

    email_service = EmailService(get_settings())
    try:
        email_service.send_otp_email(email, otp_code)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {exc}") from exc

    return {"ok": True, "message": "Verification code sent to your email"}


@router.post("/forgot-password/verify-otp")
def forgot_password_verify_otp(
    payload: VerifyOtpRequest,
    db: Session = Depends(get_db),
):
    email = payload.email.lower().strip()

    existing = db.query(User).filter(User.email == email).first()
    if not existing or existing.app_role != AppRole.ADMIN.value:
        raise HTTPException(status_code=400, detail="Invalid request")

    otp_record = (
        db.query(EmailOtp)
        .filter(
            EmailOtp.email == email,
            EmailOtp.purpose == "password_reset",
            EmailOtp.is_used.is_(False),
        )
        .order_by(EmailOtp.created_at.desc())
        .first()
    )

    if not otp_record:
        raise HTTPException(status_code=400, detail="No verification code was requested for this email")

    # Check expiration (ensure comparison is timezone-aware)
    exp = otp_record.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    if exp < datetime.now(UTC):
        raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new one.")

    if otp_record.attempts >= 5:
        otp_record.is_used = True
        db.commit()
        raise HTTPException(status_code=400, detail="Too many invalid attempts. Please request a new verification code.")

    if otp_record.otp_hash != hash_token(payload.otp.strip()):
        otp_record.attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid verification code")

    # DO NOT set is_used to True yet, let the final reset endpoint consume it
    return {"ok": True, "message": "Code verified"}


@router.post("/forgot-password/reset")
def forgot_password_reset(
    payload: ForgotPasswordResetRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    email = payload.email.lower().strip()

    existing = db.query(User).filter(User.email == email).first()
    if not existing or existing.app_role != AppRole.ADMIN.value:
        raise HTTPException(status_code=400, detail="Invalid request")

    otp_record = (
        db.query(EmailOtp)
        .filter(
            EmailOtp.email == email,
            EmailOtp.purpose == "password_reset",
            EmailOtp.is_used.is_(False),
        )
        .order_by(EmailOtp.created_at.desc())
        .first()
    )

    if not otp_record:
        raise HTTPException(status_code=400, detail="No verification code was requested for this email")

    # Check expiration (ensure comparison is timezone-aware)
    exp = otp_record.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    if exp < datetime.now(UTC):
        raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new one.")

    if otp_record.attempts >= 5:
        otp_record.is_used = True
        db.commit()
        raise HTTPException(status_code=400, detail="Too many invalid attempts. Please request a new verification code.")

    if otp_record.otp_hash != hash_token(payload.otp.strip()):
        otp_record.attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid verification code")

    otp_record.is_used = True

    # Reset password
    auth = AuthenticationService(db, get_settings())
    try:
        auth.reset_password(existing, payload.new_password, force_change=False)
    except HTTPException as e:
        db.rollback()
        raise e

    db.commit()

    AuditService(db).record(
        actor_user_id=existing.id,
        action="reset_password",
        request_id=request.headers.get("X-Request-ID", "reset"),
        status=AuditStatus.SUCCESS.value,
        ip=request.client.host if request.client else None,
        secret=get_settings().session_secret,
    )

    return {"ok": True, "message": "Password successfully reset"}


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    rate_limit_login(request)
    settings = get_settings()
    client_key = f"{payload.identifier.lower()}|{request.client.host if request.client else 'unknown'}"
    auth = AuthenticationService(db, settings)
    user = auth.authenticate(payload.identifier, payload.password, client_key, payload.company_name)
    auth.issue_session(response, user)
    auth_user = auth.to_auth_user(user)
    AuditService(db).record(
        actor_user_id=user.id,
        action="login",
        request_id=request.headers.get("X-Request-ID", "login"),
        status=AuditStatus.SUCCESS.value,
        ip=request.client.host if request.client else None,
        secret=settings.session_secret,
    )
    return {
        "user": UserPublic(
            id=auth_user.id,
            unique_identifier=auth_user.unique_identifier,
            email=auth_user.email,
            full_name=auth_user.full_name,
            app_role=auth_user.app_role,
            department_id=auth_user.department_id,
            is_active=auth_user.is_active,
            must_change_password=auth_user.must_change_password,
            company_name=auth_user.company_name,
            role_names=auth_user.role_names,
            group_names=auth_user.group_names,
        ).model_dump()
    }


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    require_csrf(request)
    AuthenticationService(db).logout(request, response)
    return {"ok": True}


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    require_csrf(request)
    AuthenticationService(db).refresh_session(request, response)
    return {"ok": True}


@router.get("/me")
def me(user=Depends(get_current_user)):
    return UserPublic(
        id=user.id,
        unique_identifier=user.unique_identifier,
        email=user.email,
        full_name=user.full_name,
        app_role=user.app_role,
        department_id=user.department_id,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        company_name=user.company_name,
        role_names=user.role_names,
        group_names=user.group_names,
    ).model_dump()


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_csrf(request)
    from app.models.user import User

    db_user = db.get(User, user.id)
    if db_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    auth = AuthenticationService(db)
    auth.change_password(db_user, payload.current_password, payload.new_password)
    auth.issue_session(response, db_user)

    from app.audit.service import AuditService
    AuditService(db).record(
        actor_user_id=db_user.id,
        tenant_id=db_user.tenant_id,
        action="change_password",
        request_id=request.headers.get("X-Request-ID", db_user.app_role),
        status=AuditStatus.SUCCESS.value,
        detail=db_user.full_name,
        ip=request.client.host if request.client else None,
        secret=get_settings().session_secret,
    )
    return {"ok": True}
