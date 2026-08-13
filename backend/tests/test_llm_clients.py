import json

import httpx
import pytest

from app.services.llm_clients import (
    AnthropicClient,
    BaseLLMClient,
    LLMClientError,
    LocalClient,
    OpenAIClient,
    create_llm_client,
)


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    async def _instant(attempt, retry_after=None):
        return None

    monkeypatch.setattr(BaseLLMClient, "_backoff", staticmethod(_instant))


def openai_payload(text="hello"):
    return {
        "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2},
    }


def anthropic_payload(text="hello"):
    return {
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": 3, "output_tokens": 2},
    }


def make_transport(responses):
    """Transport serving scripted (status, payload) responses in order,
    recording each request body."""
    class _T(httpx.AsyncBaseTransport):
        def __init__(self):
            self.requests = []
            self.scripted = list(responses)

        async def handle_async_request(self, request):
            self.requests.append(json.loads(request.content))
            status, payload = (
                self.scripted.pop(0) if self.scripted else (200, openai_payload())
            )
            return httpx.Response(status, json=payload)

    return _T()


async def test_openai_success():
    transport = make_transport([(200, openai_payload("hi there"))])
    client = OpenAIClient("key", "gpt-test", transport=transport)
    try:
        res = await client.complete("prompt", {"temperature": 0})
    finally:
        await client.aclose()
    assert res.text == "hi there"
    assert res.input_tokens == 3 and res.output_tokens == 2
    assert transport.requests[0]["temperature"] == 0
    assert transport.requests[0]["messages"] == [{"role": "user", "content": "prompt"}]


async def test_openai_retries_on_429_then_succeeds():
    transport = make_transport(
        [(429, {"error": "rate limited"}), (200, openai_payload("recovered"))]
    )
    client = OpenAIClient("key", "gpt-test", transport=transport)
    try:
        res = await client.complete("prompt")
    finally:
        await client.aclose()
    assert res.text == "recovered"
    assert len(transport.requests) == 2


async def test_openai_no_retry_on_401():
    transport = make_transport([(401, {"error": "bad key"})])
    client = OpenAIClient("key", "gpt-test", transport=transport)
    try:
        with pytest.raises(LLMClientError) as exc:
            await client.complete("prompt")
    finally:
        await client.aclose()
    assert "401" in str(exc.value)
    assert len(transport.requests) == 1


async def test_openai_retries_exhausted():
    transport = make_transport([(503, {}), (503, {}), (503, {})])
    client = OpenAIClient("key", "gpt-test", transport=transport)
    try:
        with pytest.raises(LLMClientError):
            await client.complete("prompt")
    finally:
        await client.aclose()
    # AGENT_EVAL_LLM_MAX_RETRIES=2 in tests -> 3 attempts total
    assert len(transport.requests) == 3


async def test_anthropic_does_not_mutate_shared_params():
    """Regression test: the old client popped max_tokens from the caller's
    dict, so concurrent tasks after the first lost their configured value."""
    transport = make_transport([(200, anthropic_payload()), (200, anthropic_payload())])
    client = AnthropicClient("key", "claude-test", transport=transport)
    shared = {"max_tokens": 123, "temperature": 0.5}
    try:
        await client.complete("a", shared)
        await client.complete("b", shared)
    finally:
        await client.aclose()
    assert shared == {"max_tokens": 123, "temperature": 0.5}
    assert transport.requests[0]["max_tokens"] == 123
    assert transport.requests[1]["max_tokens"] == 123


async def test_anthropic_system_param():
    transport = make_transport([(200, anthropic_payload())])
    client = AnthropicClient("key", "claude-test", transport=transport)
    try:
        await client.complete("prompt", {"system": "be brief"})
    finally:
        await client.aclose()
    body = transport.requests[0]
    assert body["system"] == "be brief"
    assert "system" not in [m["role"] for m in body["messages"]]


async def test_openai_system_param_becomes_message():
    transport = make_transport([(200, openai_payload())])
    client = OpenAIClient("key", "gpt-test", transport=transport)
    try:
        await client.complete("prompt", {"system": "be brief"})
    finally:
        await client.aclose()
    assert transport.requests[0]["messages"][0] == {
        "role": "system",
        "content": "be brief",
    }


async def test_timeout_param_not_sent_to_api():
    transport = make_transport([(200, openai_payload())])
    client = OpenAIClient("key", "gpt-test", transport=transport)
    try:
        await client.complete("prompt", {"timeout": 5, "max_tokens": 10})
    finally:
        await client.aclose()
    assert "timeout" not in transport.requests[0]
    assert transport.requests[0]["max_tokens"] == 10


def test_factory_dispatch():
    class Cfg:
        provider = "openai"
        api_key = "k"
        model_id = "m"
        api_base_url = None

    assert isinstance(create_llm_client(Cfg()), OpenAIClient)
    Cfg.provider = "anthropic"
    assert isinstance(create_llm_client(Cfg()), AnthropicClient)
    Cfg.provider = "local"
    assert isinstance(create_llm_client(Cfg()), LocalClient)
    Cfg.provider = "bogus"
    with pytest.raises(ValueError):
        create_llm_client(Cfg())
