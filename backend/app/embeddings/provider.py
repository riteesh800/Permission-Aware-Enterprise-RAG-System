from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod

import httpx
import numpy as np

from app.config import Settings, get_settings


class EmbeddingProvider(ABC):
    dim: int

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic local embeddings for tests and offline demos without downloading models."""

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = np.zeros(self.dim, dtype=np.float64)
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        if not tokens:
            tokens = [""]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for i in range(0, min(len(digest), self.dim)):
                vec[i % self.dim] += digest[i] / 255.0
            extra = hashlib.md5(token.encode("utf-8")).digest()
            for i, b in enumerate(extra):
                vec[(i * 7) % self.dim] += (b / 255.0) * 0.5
        norm = np.linalg.norm(vec)
        if norm == 0:
            return vec.tolist()
        return (vec / norm).tolist()


class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str, dim: int) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self.dim = dim

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    def __init__(self, base_url: str, model: str, api_key: str | None, dim: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.dim = dim

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            return HashEmbeddingProvider(self.dim).embed_texts(texts)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = httpx.post(
            f"{self.base_url}/embeddings",
            headers=headers,
            json={"model": self.model, "input": texts},
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()["data"]
        ordered = sorted(data, key=lambda item: item["index"])
        return [item["embedding"] for item in ordered]


def build_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    settings = settings or get_settings()
    if settings.embedding_provider == "local":
        try:
            return LocalEmbeddingProvider(settings.embedding_model, settings.embedding_dim)
        except Exception:
            return HashEmbeddingProvider(settings.embedding_dim)
    if settings.embedding_provider == "openai-compatible":
        return OpenAICompatibleEmbeddingProvider(
            settings.embedding_api_url or settings.openai_base_url,
            settings.embedding_model,
            settings.embedding_api_key or settings.openai_api_key,
            settings.embedding_dim,
        )
    return HashEmbeddingProvider(settings.embedding_dim)
