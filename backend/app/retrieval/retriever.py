from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, joinedload

from app.auth.service import AuthUser
from app.authorization.service import AuthorizationService
from app.config import Settings, get_settings
from app.embeddings.provider import EmbeddingProvider, build_embedding_provider
from app.models.document import Document, DocumentChunk
from app.models.enums import IngestionStatus
from app.reranking.reranker import build_reranker
from app.retrieval.vector_store import SqlVectorStore, VectorHit, bm25_search


@dataclass(frozen=True)
class AuthorizedChunk:
    chunk_id: str
    document_id: str
    document_title: str
    content: str
    score: float
    page_number: int | None
    section_title: str | None
    source_location: str | None


class Retriever:
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
        self.authz = AuthorizationService(db)
        self.reranker = build_reranker(self.settings)

    def retrieve(self, user: AuthUser, query: str) -> tuple[list[AuthorizedChunk], int]:
        """Permission filter first, then hybrid search, then authoritative re-check.

        Returns (authorized_chunks, denied_count). Denied chunks never enter context.
        """
        allowed_ids = self.authz.allowed_document_ids_subquery(user)
        if not allowed_ids:
            return [], 0
        query_vec = self.embeddings.embed_query(query)
        vector_hits = self.vectors.search(query_vec, allowed_ids, self.settings.top_k)
        keyword_hits = bm25_search(self.db, query, allowed_ids, self.settings.top_k)
        merged = _merge_hits(vector_hits, keyword_hits)
        reranked = self.reranker.rerank(query, merged, self.settings.rerank_top_k)
        authorized, denied = self._recheck(user, reranked)
        return authorized, denied

    def _recheck(self, user: AuthUser, hits: list[VectorHit]) -> tuple[list[AuthorizedChunk], int]:
        denied = 0
        out: list[AuthorizedChunk] = []
        seen: set[str] = set()
        for hit in hits:
            if hit.chunk_id in seen:
                continue
            seen.add(hit.chunk_id)
            document = (
                self.db.query(Document)
                .options(joinedload(Document.acls))
                .filter(Document.id == hit.document_id)
                .one_or_none()
            )
            if document is None:
                denied += 1
                continue
            if document.ingestion_status != IngestionStatus.COMPLETED.value or not document.is_searchable:
                denied += 1
                continue
            if not self.authz.can_read_document(user, document):
                denied += 1
                continue
            chunk = self.db.get(DocumentChunk, hit.chunk_id)
            if chunk is None or chunk.document_id != document.id:
                denied += 1
                continue
            out.append(
                AuthorizedChunk(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    document_title=document.title,
                    content=chunk.content,
                    score=hit.score,
                    page_number=chunk.page_number,
                    section_title=chunk.section_title,
                    source_location=chunk.source_location,
                )
            )
        return out, denied


def _merge_hits(vector_hits: list[VectorHit], keyword_hits: list[VectorHit]) -> list[VectorHit]:
    scores: dict[str, float] = {}
    by_id: dict[str, VectorHit] = {}

    def add(hits: list[VectorHit]) -> None:
        for rank, hit in enumerate(hits):
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (60 + rank)
            by_id[hit.chunk_id] = hit

    add(vector_hits)
    add(keyword_hits)
    merged: list[VectorHit] = []
    for chunk_id, score in scores.items():
        hit = by_id[chunk_id]
        hit.score = score
        merged.append(hit)
    merged.sort(key=lambda h: h.score, reverse=True)
    return merged
