from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import HTTPException, Request, Response, status
from sqlalchemy.orm import Session, joinedload

from app.config import Settings, get_settings
from app.models.enums import AppRole
from app.models.org import UserGroup, UserRole
from app.models.session import RefreshToken
from app.models.user import User
from app.security.crypto import (
    create_access_token,
    create_refresh_token_value,
    decode_token,
    hash_password,
    hash_token,
    new_csrf_token,
    password_meets_policy,
    verify_password,
)
from app.security.throttle import login_throttle

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
GENERIC_AUTH_ERROR = "Invalid credentials"


@dataclass
class AuthUser:
    id: str
    unique_identifier: str
    email: str
    full_name: str
    app_role: str
    department_id: str | None
    is_active: bool
    must_change_password: bool
    permission_version: int
    tenant_id: str | None = None
    company_name: str | None = None
    role_ids: list[str] = field(default_factory=list)
    role_names: list[str] = field(default_factory=list)
    group_ids: list[str] = field(default_factory=list)
    group_names: list[str] = field(default_factory=list)



class AuthenticationService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()

    def load_user_by_login(self, identifier: str) -> User | None:
        ident = identifier.strip()
        user = self.db.query(User).filter(User.unique_identifier == ident).one_or_none()
        if user:
            return user
        return self.db.query(User).filter(User.email == ident.lower()).one_or_none()

    def authenticate(self, identifier: str, password: str, client_key: str, company_name: str | None = None) -> User:
        settings = self.settings
        if login_throttle.is_limited(
            client_key, settings.login_max_attempts, settings.login_lockout_seconds
        ):
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts")

        user = self.load_user_by_login(identifier)
        if user is None or not verify_password(password, user.password_hash):
            login_throttle.register_failure(client_key)
            if user is not None:
                user.failed_login_count += 1
                if user.failed_login_count >= settings.login_max_attempts:
                    from datetime import timedelta

                    user.locked_until = datetime.now(UTC) + timedelta(seconds=settings.login_lockout_seconds)
                self.db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR)

        if user.locked_until and user.locked_until > datetime.now(UTC):
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts")
        if not user.is_active:
            login_throttle.register_failure(client_key)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR)

        if user.app_role == AppRole.EMPLOYEE.value:
            if not company_name:
                login_throttle.register_failure(client_key)
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Company name is required for employee login")
            from app.models.org import Tenant
            tenant = self.db.get(Tenant, user.tenant_id) if user.tenant_id else None
            if not tenant or tenant.name.strip().lower() != company_name.strip().lower():
                login_throttle.register_failure(client_key)
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR)

        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = datetime.now(UTC)
        self.db.commit()
        login_throttle.register_success(client_key)
        return user

    def issue_session(self, response: Response, user: User) -> None:
        access = create_access_token(
            self.settings, user.id, user.app_role, user.permission_version
        )
        refresh = create_refresh_token_value()
        csrf = new_csrf_token()
        expires = datetime.now(UTC)
        from datetime import timedelta

        expires = expires + timedelta(days=self.settings.refresh_token_days)
        record = RefreshToken(user_id=user.id, token_hash=hash_token(refresh), expires_at=expires)
        self.db.add(record)
        self.db.commit()
        self._set_auth_cookies(response, access, refresh, csrf)

    def refresh_session(self, request: Request, response: Response) -> User:
        raw = request.cookies.get(REFRESH_COOKIE)
        if not raw:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        record = (
            self.db.query(RefreshToken)
            .filter(RefreshToken.token_hash == hash_token(raw), RefreshToken.revoked.is_(False))
            .one_or_none()
        )
        if record is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        exp = record.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        if exp < datetime.now(UTC):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        user = self.db.get(User, record.user_id)
        if user is None or not user.is_active:
            record.revoked = True
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        record.revoked = True
        self.db.commit()
        self.issue_session(response, user)
        return user

    def logout(self, request: Request, response: Response) -> None:
        raw = request.cookies.get(REFRESH_COOKIE)
        if raw:
            record = (
                self.db.query(RefreshToken)
                .filter(RefreshToken.token_hash == hash_token(raw))
                .one_or_none()
            )
            if record:
                record.revoked = True
                self.db.commit()
        self.clear_cookies(response)

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if not password_meets_policy(new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters and contain a mix of letters and numbers",
            )
        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        user.permission_version += 1
        self._revoke_all_refresh(user.id)
        self.db.commit()

    def reset_password(self, user: User, new_password: str, force_change: bool = True) -> None:
        if not password_meets_policy(new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters and contain a mix of letters and numbers",
            )
        user.password_hash = hash_password(new_password)
        user.must_change_password = force_change
        user.permission_version += 1
        self._revoke_all_refresh(user.id)
        self.db.commit()

    def disable_user(self, user: User, active: bool) -> None:
        user.is_active = active
        user.permission_version += 1
        if not active:
            self._revoke_all_refresh(user.id)
        self.db.commit()

    def to_auth_user(self, user: User) -> AuthUser:
        from app.models.org import Tenant
        tenant = self.db.get(Tenant, user.tenant_id) if user.tenant_id else None
        company_name = tenant.name if tenant else None
        
        roles = (
            self.db.query(UserRole)
            .options(joinedload(UserRole.role))
            .filter(UserRole.user_id == user.id)
            .all()
        )
        groups = (
            self.db.query(UserGroup)
            .options(joinedload(UserGroup.group))
            .filter(UserGroup.user_id == user.id)
            .all()
        )
        role_names = [r.role.name for r in roles if r.role]
        if user.department:
            role_names.append(user.department.name)
        return AuthUser(
            id=user.id,
            unique_identifier=user.unique_identifier,
            email=user.email,
            full_name=user.full_name,
            app_role=user.app_role,
            department_id=user.department_id,
            is_active=user.is_active,
            must_change_password=user.must_change_password,
            permission_version=user.permission_version,
            tenant_id=user.tenant_id or user.id,
            company_name=company_name,
            role_ids=[r.role_id for r in roles],
            role_names=role_names,
            group_ids=[g.group_id for g in groups],
            group_names=[g.group.name for g in groups if g.group],
        )


    def _revoke_all_refresh(self, user_id: str) -> None:
        self.db.query(RefreshToken).filter(RefreshToken.user_id == user_id).update({"revoked": True})

    def _cookie_kwargs(self) -> dict:
        kwargs: dict = {
            "httponly": True,
            "secure": self.settings.cookie_secure,
            "samesite": self.settings.cookie_samesite,
            "path": "/",
        }
        if self.settings.cookie_domain:
            kwargs["domain"] = self.settings.cookie_domain
        return kwargs

    def _set_auth_cookies(self, response: Response, access: str, refresh: str, csrf: str) -> None:
        kwargs = self._cookie_kwargs()
        response.set_cookie(ACCESS_COOKIE, access, max_age=self.settings.access_token_minutes * 60, **kwargs)
        response.set_cookie(
            REFRESH_COOKIE,
            refresh,
            max_age=self.settings.refresh_token_days * 86400,
            **kwargs,
        )
        csrf_kwargs = {**kwargs, "httponly": False}
        response.set_cookie(CSRF_COOKIE, csrf, max_age=self.settings.refresh_token_days * 86400, **csrf_kwargs)

    def clear_cookies(self, response: Response) -> None:
        for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
            response.delete_cookie(name, path="/")


def current_user_from_request(db: Session, request: Request, settings: Settings) -> AuthUser:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    payload = decode_token(settings, token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    user = db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    if int(payload.get("tv", -1)) != user.permission_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return AuthenticationService(db, settings).to_auth_user(user)


def require_csrf(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get("X-CSRF-Token")
    if not cookie or not header or cookie != header:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def require_admin(user: AuthUser) -> None:
    if user.app_role != AppRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
