"""OpenAI embedding helpers for retrieval memory."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from typing import Any

from llm.json_client import make_client

logger = logging.getLogger(__name__)

OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
MEMORY_EMBEDDING_DIM = int(os.getenv("MEMORY_EMBEDDING_DIM", "768"))


class Embedder:
    """Fail-open wrapper around OpenAI text embeddings (768-d)."""

    def __init__(
        self,
        client: Any | None = None,
        *,
        model: str = OPENAI_EMBEDDING_MODEL,
        output_dimensionality: int = MEMORY_EMBEDDING_DIM,
    ):
        self._client = client
        self._model = model
        self.output_dimensionality = output_dimensionality

    def embed_document(self, *, title: str, text: str) -> list[float]:
        """Embed a stored document for retrieval."""
        return self._embed(text=self._prepare_text(title, text))

    def embed_query(self, text: str) -> list[float]:
        """Embed a query for retrieval."""
        return self._embed(text=self._prepare_text("", text))

    def generate_embedding(self, text: str) -> list[float]:
        """Convenience alias for embed_query — use when task context is generic."""
        return self.embed_query(text)

    def _embed(self, *, text: str) -> list[float]:
        if not text:
            return []

        try:
            response = self._openai_client.embeddings.create(
                model=self._model,
                input=text[:8000],
                dimensions=self.output_dimensionality,
            )
            values = _extract_first_embedding_values(response)
            if len(values) > self.output_dimensionality:
                values = values[: self.output_dimensionality]
            if len(values) != self.output_dimensionality:
                logger.warning(
                    "OpenAI embedding skipped: expected %d dimensions, got %d",
                    self.output_dimensionality,
                    len(values),
                )
                return []
            return values
        except Exception as exc:
            logger.warning("OpenAI embedding failed; memory step will be skipped: %s", exc)
            return []

    @property
    def _openai_client(self):
        if self._client is None:
            self._client = make_client()
        return self._client

    @staticmethod
    def _prepare_text(title: str, text: str) -> str:
        parts = [title.strip(), text.strip()]
        return "\n\n".join(part for part in parts if part)


GeminiEmbedder = Embedder


def _extract_first_embedding_values(response: object) -> list[float]:
    data = getattr(response, "data", None)
    if data:
        first = data[0]
        return _coerce_values(getattr(first, "embedding", first))

    embeddings = getattr(response, "embeddings", None)
    if embeddings:
        first = embeddings[0]
        return _coerce_values(getattr(first, "values", getattr(first, "embedding", first)))

    embedding = getattr(response, "embedding", None)
    if embedding is not None:
        return _coerce_values(getattr(embedding, "values", embedding))

    if isinstance(response, dict):
        rows = response.get("data")
        if rows:
            first = rows[0]
            if isinstance(first, dict):
                return _coerce_values(first.get("embedding", []))
            return _coerce_values(getattr(first, "embedding", first))
        embeddings = response.get("embeddings")
        if embeddings:
            first = embeddings[0]
            if isinstance(first, dict):
                return _coerce_values(first.get("values", first.get("embedding", [])))
            return _coerce_values(first)
        embedding = response.get("embedding")
        if isinstance(embedding, dict):
            return _coerce_values(embedding.get("values", []))
        if embedding is not None:
            return _coerce_values(embedding)

    return []


def _coerce_values(values: object) -> list[float]:
    if not isinstance(values, Iterable) or isinstance(values, (str, bytes)):
        return []
    try:
        return [float(value) for value in values]
    except TypeError:
        return []
