from llm.embedding_client import GeminiEmbedder


class _Embedding:
    def __init__(self, values):
        self.values = values


class _Response:
    def __init__(self, values):
        self.embeddings = [_Embedding(values)]


class _Models:
    def __init__(self, values=None, exc=None):
        self.values = values or [0.1] * 768
        self.exc = exc
        self.calls = []

    def embed_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc:
            raise self.exc
        return _Response(self.values)


class _Client:
    def __init__(self, models):
        self.models = models


def test_gemini_embedder_returns_configured_768_dimensions():
    models = _Models(values=[0.2] * 768)
    embedder = GeminiEmbedder(client=_Client(models), output_dimensionality=768)

    result = embedder.embed_document(title="NVIDIA GPU supply", text="HBM demand rises.")

    assert len(result) == 768
    assert result[0] == 0.2
    assert models.calls[0]["model"]


def test_gemini_embedder_exception_returns_empty_vector():
    embedder = GeminiEmbedder(
        client=_Client(_Models(exc=RuntimeError("quota"))),
        output_dimensionality=768,
    )

    assert embedder.embed_query("AI infrastructure") == []
