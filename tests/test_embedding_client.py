from llm.embedding_client import Embedder


class _Row:
    def __init__(self, values):
        self.embedding = values


class _Response:
    def __init__(self, values):
        self.data = [_Row(values)]


class _Embeddings:
    def __init__(self, values=None, exc=None):
        self.values = values or [0.1] * 768
        self.exc = exc
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc:
            raise self.exc
        return _Response(self.values)


class _Client:
    def __init__(self, embeddings):
        self.embeddings = embeddings


def test_embedder_returns_configured_768_dimensions():
    embeddings = _Embeddings(values=[0.2] * 768)
    embedder = Embedder(client=_Client(embeddings), output_dimensionality=768)

    result = embedder.embed_document(title="NVIDIA GPU supply", text="HBM demand rises.")

    assert len(result) == 768
    assert result[0] == 0.2
    assert embeddings.calls[0]["model"]
    assert embeddings.calls[0]["dimensions"] == 768


def test_embedder_exception_returns_empty_vector():
    embedder = Embedder(
        client=_Client(_Embeddings(exc=RuntimeError("quota"))),
        output_dimensionality=768,
    )

    assert embedder.embed_query("AI infrastructure") == []
