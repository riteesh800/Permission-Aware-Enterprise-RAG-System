from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.audit.service import AuditService
from app.config import get_settings
from app.database import get_db
from app.deps import get_admin_user, get_admin_user_readonly
from app.ingestion.service import IngestionService
from app.models.document import Document, DocumentAcl
from app.models.enums import IngestionStatus
from app.schemas import AclEntry, PatchDocumentRequest

router = APIRouter(prefix="/api/admin/documents", tags=["admin-documents"])


def _doc_out(doc: Document) -> dict:
    return {
        "id": doc.id,
        "external_id": doc.external_id,
        "filename": doc.filename,
        "title": doc.title,
        "document_type": doc.document_type,
        "owner_user_id": doc.owner_user_id,
        "department_id": doc.department_id,
        "checksum": doc.checksum,
        "version": doc.version,
        "ingestion_status": doc.ingestion_status,
        "ingestion_error": doc.ingestion_error,
        "is_searchable": doc.is_searchable,
        "acls": [
            {
                "id": a.id,
                "principal_type": a.principal_type,
                "principal_id": a.principal_id,
                "permission": a.permission,
                "department_scoped": a.department_scoped,
            }
            for a in (doc.acls or [])
        ],
    }


@router.post("")
async def upload_document(
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
    file: UploadFile = File(...),
    title: str = Form(...),
    document_type: str = Form("file"),
    owner_user_id: str | None = Form(None),
    department_id: str | None = Form(None),
    acls_json: str = Form("[]"),
):
    data = await file.read()
    try:
        acls = json.loads(acls_json)
        if not isinstance(acls, list):
            raise ValueError("acls")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ACL payload") from None
    admin_tenant = admin.tenant_id or admin.id
    try:
        document = IngestionService(db).store_and_ingest(
            filename=file.filename or "upload.bin",
            content_type=file.content_type,
            data=data,
            title=title,
            document_type=document_type,
            owner_user_id=owner_user_id or None,
            department_id=department_id or None,
            acls=acls,
            tenant_id=admin_tenant,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to process request: {exc}") from None
    document = db.query(Document).options(joinedload(Document.acls)).filter(Document.id == document.id).one()
    AuditService(db).record(
        actor_user_id=admin.id,
        tenant_id=admin_tenant,
        action="upload_document",
        request_id=request.headers.get("X-Request-ID", "admin"),
        status="SUCCESS",
        document_id=document.id,
        secret=get_settings().session_secret,
    )
    return _doc_out(document)


@router.get("")
def list_documents(admin=Depends(get_admin_user_readonly), db: Session = Depends(get_db)):
    admin_tenant = admin.tenant_id or admin.id
    docs = (
        db.query(Document)
        .options(joinedload(Document.acls))
        .filter(Document.tenant_id == admin_tenant)
        .order_by(Document.created_at.desc())
        .all()
    )
    return [_doc_out(d) for d in docs]


@router.get("/{document_id}")
def get_document(document_id: str, admin=Depends(get_admin_user_readonly), db: Session = Depends(get_db)):
    admin_tenant = admin.tenant_id or admin.id
    doc = (
        db.query(Document)
        .options(joinedload(Document.acls))
        .filter(Document.id == document_id, Document.tenant_id == admin_tenant)
        .one_or_none()
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Not found")
    return _doc_out(doc)


@router.patch("/{document_id}")
def patch_document(
    document_id: str,
    payload: PatchDocumentRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    admin_tenant = admin.tenant_id or admin.id
    doc = (
        db.query(Document)
        .options(joinedload(Document.acls))
        .filter(Document.id == document_id, Document.tenant_id == admin_tenant)
        .one_or_none()
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Not found")
    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        doc.title = data["title"]
    if "department_id" in data:
        doc.department_id = data["department_id"]
    if "owner_user_id" in data:
        doc.owner_user_id = data["owner_user_id"]
    if data.get("disabled") is True:
        doc.ingestion_status = IngestionStatus.DISABLED.value
        doc.is_searchable = False
    if data.get("disabled") is False and doc.ingestion_status == IngestionStatus.DISABLED.value:
        doc.ingestion_status = IngestionStatus.COMPLETED.value
        doc.is_searchable = True
    if "acls" in data and data["acls"] is not None:
        db.query(DocumentAcl).filter(DocumentAcl.document_id == doc.id).delete()
        for acl in data["acls"]:
            entry = acl if isinstance(acl, dict) else acl
            if not isinstance(entry, dict):
                entry = AclEntry.model_validate(entry).model_dump()
            db.add(
                DocumentAcl(
                    document_id=doc.id,
                    principal_type=entry["principal_type"],
                    principal_id=entry.get("principal_id"),
                    permission=entry.get("permission", "READ"),
                    department_scoped=bool(entry.get("department_scoped", False)),
                )
            )
        doc.permission_version += 1
    db.commit()
    doc = db.query(Document).options(joinedload(Document.acls)).filter(Document.id == document_id).one()
    AuditService(db).record(
        actor_user_id=admin.id,
        tenant_id=admin_tenant,
        action="patch_document",
        request_id=request.headers.get("X-Request-ID", "admin"),
        status="SUCCESS",
        document_id=doc.id,
        secret=get_settings().session_secret,
    )
    return _doc_out(doc)


@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    admin_tenant = admin.tenant_id or admin.id
    doc = db.get(Document, document_id)
    if doc is None or doc.tenant_id != admin_tenant:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(doc)
    db.commit()
    AuditService(db).record(
        actor_user_id=admin.id,
        tenant_id=admin_tenant,
        action="delete_document",
        request_id=request.headers.get("X-Request-ID", "admin"),
        status="SUCCESS",
        document_id=document_id,
        secret=get_settings().session_secret,
    )
    return {"ok": True}


@router.post("/{document_id}/reindex")
def reindex(
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    admin_tenant = admin.tenant_id or admin.id
    doc = db.get(Document, document_id)
    if doc is None or doc.tenant_id != admin_tenant:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        IngestionService(db).reindex(doc)
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to process request") from None
    doc = db.query(Document).options(joinedload(Document.acls)).filter(Document.id == document_id).one()
    AuditService(db).record(
        actor_user_id=admin.id,
        tenant_id=admin_tenant,
        action="reindex_document",
        request_id=request.headers.get("X-Request-ID", "admin"),
        status="SUCCESS",
        document_id=document_id,
        secret=get_settings().session_secret,
    )
    return _doc_out(doc)

