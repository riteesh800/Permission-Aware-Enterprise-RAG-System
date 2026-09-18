from __future__ import annotations

import json
import math
import re
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass

import numpy as np
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import is_postgres
from app.models.document import DocumentChunk

_TOKEN = re.compile(r"[a-z0-9]{3,}")


@dataclass
class VectorHit:
    chunk_id: str
    document_id: str
    score: float
    content: str
    chunk_index: int
    section_title: str | None
    page_number: int | None
    source_location: str | None


class VectorStore(ABC):
    @abstractmethod
    def upsert_chunks(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_document_chunks(self, document_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        allowed_document_ids: list[str],
        top_k: int,
    ) -> list[VectorHit]:
        raise NotImplementedError


def _to_hit(chunk: DocumentChunk, score: float) -> VectorHit:
    return VectorHit(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        score=score,
        content=chunk.content,
        chunk_index=chunk.chunk_index,
        section_title=chunk.section_title,
        page_number=chunk.page_number,
        source_location=chunk.source_location,
    )


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{float(v):.8f}" for v in values) + "]"


class SqlVectorStore(VectorStore):
    """JSON embeddings everywhere. PostgreSQL + pgvector used when available.

    Retrieval always requires an allow-list of authorized document IDs.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def _use_pgvector(self) -> bool:
        settings = get_settings()
        bind = self.db.get_bind()
        return settings.vector_db == "pgvector" and is_postgres(bind)

    def upsert_chunks(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            chunk.embedding_json = json.dumps(embedding)
        self.db.flush()
        if not self._use_pgvector():
            return
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            try:
                self.db.execute(
                    text("UPDATE document_chunks SET embedding = CAST(:v AS vector) WHERE id = :id"),
                    {"v": _vector_literal(embedding), "id": chunk.id},
                )
            except Exception:
                self.db.rollback()
                return
        self.db.flush()

    def delete_document_chunks(self, document_id: str) -> None:
        self.db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
        self.db.flush()

    def search(
        self,
        query_embedding: list[float],
        allowed_document_ids: list[str],
        top_k: int,
    ) -> list[VectorHit]:
        if not allowed_document_ids:
            return []
        if self._use_pgvector():
            hits = self._pgvector_search(query_embedding, allowed_document_ids, top_k)
            if hits is not None:
                return hits
        return self._json_search(query_embedding, allowed_document_ids, top_k)

    def _pgvector_search(
        self,
        query_embedding: list[float],
        allowed_document_ids: list[str],
        top_k: int,
    ) -> list[VectorHit] | None:
        try:
            stmt = text(
                """
                SELECT id
                FROM document_chunks
                WHERE document_id IN :ids
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:q AS vector)
                LIMIT :k
                """
            ).bindparams(bindparam("ids", expanding=True))
            result = self.db.execute(
                stmt,
                {
                    "ids": tuple(allowed_document_ids),
                    "q": _vector_literal(query_embedding),
                    "k": top_k,
                },
            )
            ids = [row[0] for row in result]
        except Exception:
            return None
        if not ids:
            return []
        chunks = self.db.query(DocumentChunk).filter(DocumentChunk.id.in_(ids)).all()
        by_id = {c.id: c for c in chunks}
        hits: list[VectorHit] = []
        q = np.array(query_embedding, dtype=np.float64)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return []
        q = q / q_norm
        for rank, chunk_id in enumerate(ids):
            chunk = by_id.get(chunk_id)
            if chunk is None or not chunk.embedding_json:
                continue
            vec = np.array(json.loads(chunk.embedding_json), dtype=np.float64)
            n = np.linalg.norm(vec)
            score = float(np.dot(q, vec / n)) if n else 1.0 / (rank + 1)
            hits.append(_to_hit(chunk, score))
        return hits

    def _json_search(
        self,
        query_embedding: list[float],
        allowed_document_ids: list[str],
        top_k: int,
    ) -> list[VectorHit]:
        q = np.array(query_embedding, dtype=np.float64)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return []
        q = q / q_norm
        chunks = (
            self.db.query(DocumentChunk)
            .filter(
                DocumentChunk.document_id.in_(allowed_document_ids),
                DocumentChunk.embedding_json.is_not(None),
            )
            .all()
        )
        scored: list[VectorHit] = []
        for chunk in chunks:
            if not chunk.embedding_json:
                continue
            vec = np.array(json.loads(chunk.embedding_json), dtype=np.float64)
            n = np.linalg.norm(vec)
            if n == 0:
                continue
            scored.append(_to_hit(chunk, float(np.dot(q, vec / n))))
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:top_k]


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def bm25_search(db: Session, query: str, allowed_document_ids: list[str], top_k: int) -> list[VectorHit]:
    """Okapi BM25 over already-authorized document chunks only."""
    if not allowed_document_ids or not query.strip():
        return []
    q_terms = tokenize(query)
    if not q_terms:
        return []
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id.in_(allowed_document_ids)).all()
    if not chunks:
        return []
    tokenized = [tokenize(chunk.content) for chunk in chunks]
    n_docs = len(chunks)
    avgdl = sum(len(toks) for toks in tokenized) / n_docs
    df: Counter[str] = Counter()
    for toks in tokenized:
        df.update(set(toks))
    k1 = 1.5
    b = 0.75
    hits: list[VectorHit] = []
    for chunk, toks in zip(chunks, tokenized, strict=True):
        if not toks:
            continue
        tf = Counter(toks)
        dl = len(toks)
        score = 0.0
        for term in q_terms:
            if term not in tf:
                continue
            idf = math.log(1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
            freq = tf[term]
            denom = freq + k1 * (1 - b + b * dl / avgdl)
            score += idf * (freq * (k1 + 1) / denom)
        if score > 0:
            hits.append(_to_hit(chunk, score))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top_k]


def lexical_search(
    db: Session, query: str, allowed_document_ids: list[str], top_k: int
) -> list[VectorHit]:
    return bm25_search(db, query, allowed_document_ids, top_k)
