from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.embeddings.provider import EmbeddingProvider, build_embedding_provider
from app.ingestion.files import (
    MalwareScanner,
    extract_chunks,
    sanitize_filename,
    sha256_bytes,
    storage_name,
    validate_upload,
)
from app.models.document import Document, DocumentAcl, DocumentChunk
from app.models.enums import IngestionStatus
from app.retrieval.vector_store import SqlVectorStore


class IngestionService:
    def __init__(
        self,
        db: Session,
        settings: Settings | None = None,
        embeddings: EmbeddingProvider | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.embeddings = embeddings or build_embedding_provider(self.settings)
        self.vectors = SqlVectorStore(db)
        self.scanner = MalwareScanner()

    def store_and_ingest(
        self,
        *,
        filename: str,
        content_type: str | None,
        data: bytes,
        title: str,
        document_type: str,
        owner_user_id: str | None,
        department_id: str | None,
        acls: list[dict],
        tenant_id: str | None = None,
    ) -> Document:
        ext = validate_upload(filename, content_type, len(data), self.settings)
        self.scanner.scan(data, filename)
        checksum = sha256_bytes(data)
        Path(self.settings.storage_path).mkdir(parents=True, exist_ok=True)
        stored = storage_name(ext)
        dest = Path(self.settings.storage_path) / stored
        dest.write_bytes(data)
        if tenant_id is None and owner_user_id:
            from app.models.user import User
            owner = self.db.get(User, owner_user_id)
            if owner and owner.tenant_id:
                tenant_id = owner.tenant_id

        document = Document(
            external_id=uuid4().hex,
            filename=sanitize_filename(filename),
            title=title or sanitize_filename(filename),
            document_type=document_type or ext.lstrip("."),
            owner_user_id=owner_user_id,
            department_id=department_id,
            tenant_id=tenant_id,
            storage_path=stored,
            checksum=checksum,
            ingestion_status=IngestionStatus.PROCESSING.value,
            is_searchable=False,
        )

        self.db.add(document)
        self.db.flush()
        for acl in acls:
            self.db.add(
                DocumentAcl(
                    document_id=document.id,
                    principal_type=acl["principal_type"],
                    principal_id=acl.get("principal_id"),
                    permission=acl.get("permission", "READ"),
                    department_scoped=bool(acl.get("department_scoped", False)),
                )
            )
        self.db.commit()
        self.db.refresh(document)
        self.ingest_document(document, data, ext)
        return document

    def ingest_document(self, document: Document, data: bytes | None = None, ext: str | None = None) -> Document:
        document.ingestion_status = IngestionStatus.PROCESSING.value
        document.is_searchable = False
        self.db.commit()
        try:
            if data is None:
                path = Path(self.settings.storage_path) / document.storage_path
                data = path.read_bytes()
            if ext is None:
                ext = Path(document.filename).suffix.lower() or Path(document.storage_path).suffix.lower()
            raw_chunks = extract_chunks(data, ext, self.settings)
            self.vectors.delete_document_chunks(document.id)
            self.db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
            self.db.flush()
            records: list[DocumentChunk] = []
            texts: list[str] = []
            for raw in raw_chunks:
                record = DocumentChunk(
                    document_id=document.id,
                    chunk_index=raw.chunk_index,
                    content=raw.content,
                    section_title=raw.section_title,
                    page_number=raw.page_number,
                    source_location=raw.source_location,
                )
                records.append(record)
                texts.append(raw.content)
            self.db.add_all(records)
            self.db.flush()
            if texts:
                embeddings = self.embeddings.embed_texts(texts)
                self.vectors.upsert_chunks(records, embeddings)
            document.ingestion_status = IngestionStatus.COMPLETED.value
            document.is_searchable = True
            document.ingestion_error = None
            document.version += 1
            self.db.commit()
        except Exception:
            document.ingestion_status = IngestionStatus.FAILED.value
            document.is_searchable = False
            document.ingestion_error = "Ingestion failed"
            self.db.commit()
            # Do not re-raise; we want to return the document with FAILED status.
        return document

    def reindex(self, document: Document) -> Document:
        path = Path(self.settings.storage_path) / document.storage_path
        data = path.read_bytes()
        ext = Path(document.filename).suffix.lower() or Path(document.storage_path).suffix.lower()
        return self.ingest_document(document, data, ext)

    def delete_document(self, document: Document) -> None:
        self.vectors.delete_document_chunks(document.id)
        self.db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
        self.db.query(DocumentAcl).filter(DocumentAcl.document_id == document.id).delete()
        self.db.delete(document)
        self.db.commit()
