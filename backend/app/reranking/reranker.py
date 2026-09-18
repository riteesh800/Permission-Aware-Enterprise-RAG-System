from __future__ import annotations

from abc import ABC, abstractmethod

from app.config import Settings, get_settings
from app.retrieval.vector_store import VectorHit


class Reranker(ABC):
    @abstractmethod
    def rerank(self, query: str, hits: list[VectorHit], top_k: int) -> list[VectorHit]:
        raise NotImplementedError


class KeywordReranker(Reranker):
    """Scores only already-authorized candidates. Never used to expand the candidate set."""

    def rerank(self, query: str, hits: list[VectorHit], top_k: int) -> list[VectorHit]:
        terms = [t.lower() for t in query.split() if t.strip()]
        scored: list[tuple[float, VectorHit]] = []
        for hit in hits:
            text = hit.content.lower()
            lexical = sum(text.count(term) for term in terms)
            combined = hit.score + (0.15 * lexical)
            scored.append((combined, hit))
        scored.sort(key=lambda item: item[0], reverse=True)
        out: list[VectorHit] = []
        for score, hit in scored[:top_k]:
            hit.score = score
            out.append(hit)
        return out


class LocalCrossEncoderReranker(Reranker):
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(model_name)

    def rerank(self, query: str, hits: list[VectorHit], top_k: int) -> list[VectorHit]:
        if not hits:
            return []
        pairs = [(query, hit.content) for hit in hits]
        scores = self._model.predict(pairs)
        ranked = sorted(zip(scores, hits, strict=True), key=lambda item: float(item[0]), reverse=True)
        out: list[VectorHit] = []
        for score, hit in ranked[:top_k]:
            hit.score = float(score)
            out.append(hit)
        return out


def build_reranker(settings: Settings | None = None) -> Reranker:
    settings = settings or get_settings()
    if settings.reranker_provider == "local":
        try:
            return LocalCrossEncoderReranker(settings.reranker_model)
        except Exception:
            return KeywordReranker()
    return KeywordReranker()
