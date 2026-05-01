"""Gemini embedding helpers for retrieval memory."""

from __future__ import annotations

import logging
import os
from typing import Any

from llm.gemini_client import make_client

logger = logging.getLogger(__name__)

GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
MEMORY_EMBEDDING_DIM = int(os.getenv("MEMORY_EMBEDDING_DIM", "768"))


class GeminiEmbedder:
    """Small fail-open wrapper around Gemini text embeddings."""

    def __init__(
        self,
        client: Any | None = None,
        *,
        model: str = GEMINI_EMBEDDING_MODEL,
        output_dimensionality: int = MEMORY_EMBEDDING_DIM,
    ):
        self._client = client
        self._model = model
        self.output_dimensionality = output_dimensionality

    def embed_document(self, *, title: str, text: str) -> list[float]:
        """Embed a stored document for retrieval."""
        return self._embed(
            text=self._prepare_text(title, text),
            task_type="RETRIEVAL_DOCUMENT",
            title=title,
        )

    def embed_query(self, text: str) -> list[float]:
        """Embed a query for retrieval."""
        return self._embed(text=self._prepare_text("", text), task_type="RETRIEVAL_QUERY")

    def _embed(self, *, text: str, task_type: str, title: str = "") -> list[float]:
        if not text:
            return []

        try:
            from google.genai import types  # noqa: PLC0415 - lazy import for test stability

            config_kwargs: dict[str, Any] = {
                "task_type": task_type,
                "output_dimensionality": self.output_dimensionality,
            }
            if title and task_type == "RETRIEVAL_DOCUMENT":
                config_kwargs["title"] = title[:512]

            response = self._gemini_client.models.embed_content(
                model=self._model,
                contents=text[:8000],
                config=types.EmbedContentConfig(**config_kwargs),
            )
            values = _extract_first_embedding_values(response)
            if len(values) > self.output_dimensionality:
                values = values[: self.output_dimensionality]
            if len(values) != self.output_dimensionality:
                logger.warning(
                    "Gemini embedding skipped: expected %d dimensions, got %d",
                    self.output_dimensionality,
                    len(values),
                )
                return []
            return values
        except Exception as exc:
            logger.warning("Gemini embedding failed; memory step will be skipped: %s", exc)
            return []

    @property
    def _gemini_client(self):
        if self._client is None:
            self._client = make_client()
        return self._client

    @staticmethod
    def _prepare_text(title: str, text: str) -> str:
        parts = [title.strip(), text.strip()]
        return "\n\n".join(part for part in parts if part)


def _extract_first_embedding_values(response: object) -> list[float]:
    embeddings = getattr(response, "embeddings", None)
    if embeddings:
        first = embeddings[0]
        return _coerce_values(getattr(first, "values", first))

    embedding = getattr(response, "embedding", None)
    if embedding is not None:
        return _coerce_values(getattr(embedding, "values", embedding))

    if isinstance(response, dict):
        embeddings = response.get("embeddings")
        if embeddings:
            first = embeddings[0]
            if isinstance(first, dict):
                return _coerce_values(first.get("values", []))
            return _coerce_values(first)
        embedding = response.get("embedding")
        if isinstance(embedding, dict):
            return _coerce_values(embedding.get("values", []))
        if embedding is not None:
            return _coerce_values(embedding)

    return []


def _coerce_values(values: object) -> list[float]:
    if values is None:
        return []
    try:
        return [float(value) for value in values]
    except TypeError:
        return []
