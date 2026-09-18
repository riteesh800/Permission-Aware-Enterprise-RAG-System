from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        actor_user_id: str | None,
        action: str,
        request_id: str,
        status: str,
        query: str | None = None,
        document_id: str | None = None,
        result_count: int | None = None,
        denied_result_count: int | None = None,
        ip: str | None = None,
        detail: str | None = None,
        secret: str = "audit",
        tenant_id: str | None = None,
    ) -> AuditLog:
        query_hash = None
        if query:
            query_hash = hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()
        ip_hash = None
        if ip:
            ip_hash = hashlib.sha256(f"{secret}:{ip}".encode()).hexdigest()
        log = AuditLog(
            timestamp=datetime.now(UTC),
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            request_id=request_id,
            query_hash=query_hash,
            document_id=document_id,
            result_count=result_count,
            denied_result_count=denied_result_count,
            status=status,
            ip_hash=ip_hash,
            detail=detail,
        )

        self.db.add(log)
        self.db.commit()
        return log
