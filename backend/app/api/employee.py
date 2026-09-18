from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os
from pathlib import Path

from app.audit.service import AuditService
from app.authorization.service import AuthorizationService
from app.database import get_db
from app.deps import get_current_user
from app.models.document import Document
from app.config import get_settings

router = APIRouter(prefix="/api/employee", tags=["employee"])


def _doc_out(doc: Document) -> dict:
    return {
        "id": doc.id,
        "filename": doc.filename,
        "title": doc.title,
        "document_type": doc.document_type,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.get("/documents")
def list_employee_documents(user=Depends(get_current_user), db: Session = Depends(get_db)):
    auth_service = AuthorizationService(db)
    allowed_doc_ids = auth_service.allowed_document_ids_subquery(user)
    if not allowed_doc_ids:
        return []
    docs = db.query(Document).filter(Document.id.in_(allowed_doc_ids)).order_by(Document.created_at.desc()).all()
    return [_doc_out(doc) for doc in docs]


@router.get("/documents/{document_id}/download")
def download_document(document_id: str, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    auth_service = AuthorizationService(db)
    
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
        
    decision = auth_service.decide(auth_service.context_for(user), doc)
    if not decision.allowed:
        raise HTTPException(status_code=403, detail="Access denied")
        
    settings = get_settings()
    full_path = Path(settings.storage_path) / doc.storage_path

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Document file missing from storage")

    AuditService(db).record(
        actor_user_id=user.id,
        tenant_id=user.tenant_id,
        action="download_document",
        request_id=request.headers.get("X-Request-ID", "employee"),
        status="SUCCESS",
        document_id=doc.id,
        secret=settings.session_secret,
    )

    return FileResponse(
        path=str(full_path),
        filename=doc.filename,
        media_type="application/octet-stream"
    )
