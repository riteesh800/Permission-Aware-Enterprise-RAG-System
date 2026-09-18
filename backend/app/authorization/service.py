from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, joinedload

from app.auth.service import AuthUser
from app.models.document import Document, DocumentAcl
from app.models.enums import AclPermission, IngestionStatus, PrincipalType


@dataclass(frozen=True)
class AuthorizationContext:
    user_id: str
    role_ids: tuple[str, ...]
    role_names: tuple[str, ...]
    group_ids: tuple[str, ...]
    group_names: tuple[str, ...]
    department_id: str | None
    is_admin: bool
    permission_version: int
    tenant_id: str | None = None


@dataclass
class AccessDecision:
    allowed: bool
    reason: str


class AuthorizationService:
    """Authoritative document access. Deny overrides allow. Never trust client-supplied roles."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def context_for(self, user: AuthUser) -> AuthorizationContext:
        return AuthorizationContext(
            user_id=user.id,
            role_ids=tuple(user.role_ids),
            role_names=tuple(name.lower() for name in user.role_names),
            group_ids=tuple(user.group_ids),
            group_names=tuple(name.lower() for name in user.group_names),
            department_id=user.department_id,
            is_admin=user.app_role == "ADMIN",
            permission_version=user.permission_version,
            tenant_id=user.tenant_id,
        )

    def can_read_document(self, user: AuthUser, document: Document) -> bool:
        return self.decide(self.context_for(user), document).allowed

    def decide(self, ctx: AuthorizationContext, document: Document) -> AccessDecision:
        if document.tenant_id and document.tenant_id != ctx.tenant_id:
            return AccessDecision(False, "cross_tenant_denied")
        if document.ingestion_status == IngestionStatus.DISABLED.value:
            return AccessDecision(False, "disabled")
        if not document.is_searchable and document.ingestion_status != IngestionStatus.COMPLETED.value:
            return AccessDecision(False, "not_searchable")

        acls = list(document.acls) if document.acls is not None else []
        if not acls:
            acls = (
                self.db.query(DocumentAcl).filter(DocumentAcl.document_id == document.id).all()
            )

        if self._denied(ctx, document, acls):
            return AccessDecision(False, "explicit_deny")
        if document.owner_user_id and document.owner_user_id == ctx.user_id:
            return AccessDecision(True, "owner")

        if self._allowed(ctx, document, acls):
            return AccessDecision(True, "acl_allow")

        return AccessDecision(False, "no_matching_acl")

    def filter_documents(self, user: AuthUser, documents: list[Document]) -> list[Document]:
        ctx = self.context_for(user)
        return [doc for doc in documents if self.decide(ctx, doc).allowed]

    def allowed_document_ids_subquery(self, user: AuthUser):
        """Return SQL-usable list of document IDs the user may read.

        For correctness we evaluate ACLs in Python against candidate IDs after a
        filtered pre-query, then callers re-check. Hybrid retrieval still applies
        this filter before LLM context.
        """
        ctx = self.context_for(user)
        query = (
            self.db.query(Document)
            .options(joinedload(Document.acls))
            .filter(
                Document.is_searchable.is_(True),
                Document.ingestion_status == IngestionStatus.COMPLETED.value,
            )
        )
        if user.tenant_id:
            query = query.filter(
                (Document.tenant_id == user.tenant_id) | (Document.tenant_id.is_(None))
            )
        docs = query.all()
        return [doc.id for doc in docs if self.decide(ctx, doc).allowed]


    def _principal_matches(self, ctx: AuthorizationContext, document: Document, acl: DocumentAcl) -> bool:
        ptype = acl.principal_type
        pid = acl.principal_id
        if ptype == PrincipalType.PUBLIC.value:
            return True
        if ptype == PrincipalType.USER.value:
            return pid == ctx.user_id
        if ptype == PrincipalType.ROLE.value:
            match = pid in ctx.role_ids
            if match and acl.department_scoped:
                return ctx.department_id is not None and ctx.department_id == document.department_id
            return match
        if ptype == PrincipalType.GROUP.value:
            return pid in ctx.group_ids
        if ptype == PrincipalType.DEPARTMENT.value:
            return pid is not None and pid == ctx.department_id
        return False

    def _denied(self, ctx: AuthorizationContext, document: Document, acls: list[DocumentAcl]) -> bool:
        return any(
            acl.permission == AclPermission.DENY_READ.value
            and self._principal_matches(ctx, document, acl)
            for acl in acls
        )

    def _allowed(self, ctx: AuthorizationContext, document: Document, acls: list[DocumentAcl]) -> bool:
        return any(
            acl.permission == AclPermission.READ.value and self._principal_matches(ctx, document, acl)
            for acl in acls
        )
