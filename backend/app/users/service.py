from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.service import AuthenticationService
from app.config import get_settings
from app.models.org import Group, Role, UserGroup, UserRole
from app.models.user import User
from app.security.crypto import generate_unique_identifier, hash_password, password_meets_policy


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_user(
        self,
        *,
        email: str,
        full_name: str,
        password: str,
        department_id: str | None,
        app_role: str,
        unique_identifier: str | None,
        must_change_password: bool,
        tenant_id: str | None = None,
    ) -> User:
        if not password_meets_policy(password):
            raise HTTPException(status_code=400, detail="Password must be 6 characters or more and contain a mix of letters and numbers")
        if app_role not in {"ADMIN", "EMPLOYEE"}:
            raise HTTPException(status_code=400, detail="Invalid role")
        if app_role == "EMPLOYEE" and not department_id:
            raise HTTPException(status_code=400, detail="Employees must belong to a department")
        email_n = email.lower()
        if self.db.query(User).filter(User.email == email_n).one_or_none():
            raise HTTPException(status_code=400, detail="Unable to create user")
        ident = unique_identifier or generate_unique_identifier(get_settings().company_prefix)
        if self.db.query(User).filter(User.unique_identifier == ident).one_or_none():
            ident = generate_unique_identifier(get_settings().company_prefix)
        user = User(
            unique_identifier=ident,
            email=email_n,
            full_name=full_name,
            password_hash=hash_password(password),
            app_role=app_role,
            tenant_id=tenant_id,
            department_id=department_id,
            must_change_password=must_change_password,
            is_active=True,
        )

        self.db.add(user)
        self.db.flush()
        self.db.commit()
        self.db.refresh(user)
        return user

    def patch_user(self, user: User, data: dict) -> User:
        if "full_name" in data and data["full_name"] is not None:
            user.full_name = data["full_name"]
        if "email" in data and data["email"] is not None:
            user.email = data["email"].lower()
        if "department_id" in data:
            if user.app_role == "EMPLOYEE" and not data["department_id"]:
                raise HTTPException(status_code=400, detail="Employees must belong to a department")
            user.department_id = data["department_id"]
        if "app_role" in data and data["app_role"] is not None:
            if data["app_role"] not in {"ADMIN", "EMPLOYEE"}:
                raise HTTPException(status_code=400, detail="Invalid role")
            user.app_role = data["app_role"]
        if "must_change_password" in data and data["must_change_password"] is not None:
            user.must_change_password = data["must_change_password"]
        if "is_active" in data and data["is_active"] is not None:
            AuthenticationService(self.db).disable_user(user, data["is_active"])
        if "role_ids" in data and data["role_ids"] is not None:
            self.db.query(UserRole).filter(UserRole.user_id == user.id).delete()
            for rid in data["role_ids"]:
                self.db.add(UserRole(user_id=user.id, role_id=rid))
            user.permission_version += 1
        if "group_ids" in data and data["group_ids"] is not None:
            self.db.query(UserGroup).filter(UserGroup.user_id == user.id).delete()
            for gid in data["group_ids"]:
                self.db.add(UserGroup(user_id=user.id, group_id=gid))
            user.permission_version += 1
        self.db.commit()
        self.db.refresh(user)
        return user

    def access_summary(self, user: User) -> dict:
        from app.auth.service import AuthenticationService
        from app.authorization.service import AuthorizationService
        from app.models.document import Document
        from app.models.enums import IngestionStatus

        auth_user = AuthenticationService(self.db).to_auth_user(user)
        authz = AuthorizationService(self.db)
        query = self.db.query(Document).filter(
            Document.ingestion_status == IngestionStatus.COMPLETED.value
        )
        if user.tenant_id:
            query = query.filter(
                (Document.tenant_id == user.tenant_id) | (Document.tenant_id.is_(None))
            )
        docs = query.all()
        readable = [d.title for d in docs if authz.can_read_document(auth_user, d)]
        return {
            "department_id": user.department_id,
            "authorized_document_count": len(readable),
        }


