import httpx
import pytest

from app.stores.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingProviderError,
    OpenAIEmbeddingProvider,
)


def test_deterministic_embedding_is_reproducible() -> None:
    provider = DeterministicEmbeddingProvider(dimensions=16)
    assert provider.embed("hello") == provider.embed("hello")


def test_deterministic_embedding_differs_for_different_text() -> None:
    provider = DeterministicEmbeddingProvider(dimensions=16)
    assert provider.embed("hello") != provider.embed("goodbye")


def test_deterministic_embedding_has_configured_length() -> None:
    provider = DeterministicEmbeddingProvider(dimensions=37)
    assert len(provider.embed("hello")) == 37


def _provider_with_transport(handler: httpx.MockTransport) -> OpenAIEmbeddingProvider:
    provider = OpenAIEmbeddingProvider(
        api_key="sk-test", model="test-model", dimensions=8
    )
    provider._client = httpx.Client(
        transport=handler, base_url="https://api.openai.com/v1"
    )
    return provider


def test_openai_provider_raises_clean_error_on_http_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    provider = _provider_with_transport(httpx.MockTransport(handler))
    with pytest.raises(EmbeddingProviderError) as excinfo:
        provider.embed("hello")
    # The safe message must not leak the raw upstream error body.
    assert "boom" not in str(excinfo.value)


def test_openai_provider_raises_clean_error_on_connection_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    provider = _provider_with_transport(httpx.MockTransport(handler))
    with pytest.raises(EmbeddingProviderError):
        provider.embed("hello")


def test_openai_provider_raises_clean_error_on_malformed_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    provider = _provider_with_transport(httpx.MockTransport(handler))
    with pytest.raises(EmbeddingProviderError):
        provider.embed("hello")


def test_openai_provider_returns_embedding_on_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2, 0.3]}]})

    provider = _provider_with_transport(httpx.MockTransport(handler))
    assert provider.embed("hello") == [0.1, 0.2, 0.3]
