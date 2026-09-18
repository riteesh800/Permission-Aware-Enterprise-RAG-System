from __future__ import annotations

import re

from app.config import Settings, get_settings
from app.retrieval.retriever import AuthorizedChunk

SAFE_INSUFFICIENT = "I don't have enough authorized information to answer that."
_STOP = {
    "what",
    "which",
    "when",
    "where",
    "does",
    "have",
    "about",
    "show",
    "list",
    "tell",
    "give",
    "that",
    "this",
    "with",
    "from",
    "another",
    "employee",
    "information",
    "please",
    "exist",
    "files",
    "confidential",
}


def query_terms(query: str) -> set[str]:
    terms = set(re.findall(r"[a-z0-9]{4,}", query.lower()))
    return terms - _STOP


def relevant_authorized_chunks(query: str, chunks: list[AuthorizedChunk]) -> list[AuthorizedChunk]:
    terms = query_terms(query)
    if not terms:
        return chunks
    matched = [chunk for chunk in chunks if any(term in chunk.content.lower() for term in terms)]
    return matched


def build_authorized_context(chunks: list[AuthorizedChunk], settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if not chunks:
        return ""
    parts: list[str] = []
    used = 0
    for idx, chunk in enumerate(chunks, start=1):
        block = (
            f"SOURCE {idx}\n"
            f"Title: {chunk.document_title}\n"
            f"Page: {chunk.page_number or 'n/a'}\n"
            f"Section: {chunk.section_title or 'n/a'}\n"
            "CONTENT START\n"
            f"{chunk.content}\n"
            "CONTENT END\n"
            "END SOURCE"
        )
        tokens = max(1, len(block.split()))
        if used + tokens > settings.max_context_tokens:
            break
        parts.append(block)
        used += tokens
    return "\n\n".join(parts)


def citations_from(chunks: list[AuthorizedChunk]) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for chunk in chunks:
        key = chunk.chunk_id
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "title": chunk.document_title,
                "page": chunk.page_number,
                "section": chunk.section_title,
                "source_id": chunk.chunk_id,
            }
        )
    return out
