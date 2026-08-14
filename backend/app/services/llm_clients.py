import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Statuses worth retrying: rate limits, timeouts, and transient server errors.
RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


@dataclass
class LLMResponse:
    text: str
    latency_ms: int
    input_tokens: int
    output_tokens: int


class LLMClientError(RuntimeError):
    """Raised when the provider returns a non-retryable error or retries are exhausted."""


class BaseLLMClient(ABC):
    """Base client owning a pooled httpx.AsyncClient shared across requests.

    The previous implementation created (and TLS-handshaked) a new connection
    per task; with 10 concurrent tasks that dominated latency. One client per
    evaluation run reuses connections and enforces sane pool limits.
    """

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    self._client = httpx.AsyncClient(
                        timeout=settings.LLM_TIMEOUT_SECONDS,
                        limits=httpx.Limits(
                            max_connections=settings.MAX_CONCURRENT_TASKS + 5,
                            max_keepalive_connections=settings.MAX_CONCURRENT_TASKS,
                        ),
                        transport=self._transport,
                    )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _post_with_retry(
        self, url: str, headers: dict, body: dict, timeout: float | None
    ) -> tuple[dict, int]:
        """POST with exponential backoff on transient failures.

        Returns (response_json, latency_ms_of_successful_attempt).
        """
        client = await self._get_client()
        max_retries = max(0, settings.LLM_MAX_RETRIES)
        last_error: str = "unknown error"

        for attempt in range(max_retries + 1):
            start = time.perf_counter()
            try:
                response = await client.post(
                    url, headers=headers, json=body, timeout=timeout
                )
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_error = f"{type(e).__name__}: {e}"
                if attempt < max_retries:
                    await self._backoff(attempt, None)
                    continue
                raise LLMClientError(
                    f"Request to {url} failed after {max_retries + 1} attempts: {last_error}"
                ) from e

            elapsed_ms = int((time.perf_counter() - start) * 1000)

            if response.status_code < 400:
                return response.json(), elapsed_ms

            body_snippet = response.text[:500]
            last_error = f"HTTP {response.status_code}: {body_snippet}"
            if response.status_code in RETRYABLE_STATUS_CODES and attempt < max_retries:
                logger.warning(
                    "Retryable LLM API error (attempt %d/%d) from %s: %s",
                    attempt + 1,
                    max_retries + 1,
                    url,
                    last_error,
                )
                await self._backoff(attempt, response.headers.get("retry-after"))
                continue

            raise LLMClientError(f"LLM API error from {url}: {last_error}")

        raise LLMClientError(
            f"Request to {url} failed after {max_retries + 1} attempts: {last_error}"
        )

    @staticmethod
    async def _backoff(attempt: int, retry_after: str | None) -> None:
        delay = min(2.0**attempt, 20.0)
        if retry_after:
            try:
                delay = max(delay, min(float(retry_after), 60.0))
            except ValueError:
                pass
        await asyncio.sleep(delay + random.uniform(0, 0.25 * delay))

    @staticmethod
    def _prepare_params(params: dict | None) -> tuple[dict, float | None, str | None]:
        """Copy params (callers share one dict across concurrent tasks) and
        split out client-level options that must not reach the provider API."""
        merged = dict(params or {})
        timeout = merged.pop("timeout", None)
        if timeout is not None:
            timeout = float(timeout)
        system = merged.pop("system", None)
        return merged, timeout, system

    @abstractmethod
    async def chat(self, messages: list[dict], params: dict | None = None) -> LLMResponse:
        """Multi-turn completion. messages: [{"role": "user"|"assistant", "content": str}]."""

    async def complete(self, prompt: str, params: dict | None = None) -> LLMResponse:
        return await self.chat([{"role": "user", "content": prompt}], params)


class OpenAIClient(BaseLLMClient):
    def __init__(
        self,
        api_key: str,
        model_id: str,
        api_base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        super().__init__(transport=transport)
        self.api_key = api_key
        self.model_id = model_id
        self.api_base_url = (api_base_url or "https://api.openai.com/v1").rstrip("/")

    async def chat(self, messages: list[dict], params: dict | None = None) -> LLMResponse:
        api_params, timeout, system = self._prepare_params(params)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)
        body = {
            "model": self.model_id,
            "messages": all_messages,
            **api_params,
        }

        data, latency_ms = await self._post_with_retry(
            f"{self.api_base_url}/chat/completions", headers, body, timeout
        )

        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise LLMClientError(f"Unexpected OpenAI response shape: {e}") from e
        usage = data.get("usage") or {}
        return LLMResponse(
            text=text,
            latency_ms=latency_ms,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )


class AnthropicClient(BaseLLMClient):
    def __init__(
        self,
        api_key: str,
        model_id: str,
        api_base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        super().__init__(transport=transport)
        self.api_key = api_key
        self.model_id = model_id
        self.api_base_url = (api_base_url or "https://api.anthropic.com/v1").rstrip("/")

    async def chat(self, messages: list[dict], params: dict | None = None) -> LLMResponse:
        api_params, timeout, system = self._prepare_params(params)
        max_tokens = api_params.pop("max_tokens", 4096)
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model_id,
            "max_tokens": max_tokens,
            "messages": messages,
            **api_params,
        }
        if system:
            body["system"] = system

        data, latency_ms = await self._post_with_retry(
            f"{self.api_base_url}/messages", headers, body, timeout
        )

        try:
            blocks = data["content"]
            text = "".join(
                block.get("text", "") for block in blocks if block.get("type", "text") == "text"
            )
        except (KeyError, TypeError) as e:
            raise LLMClientError(f"Unexpected Anthropic response shape: {e}") from e
        usage = data.get("usage") or {}
        return LLMResponse(
            text=text,
            latency_ms=latency_ms,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )


class LocalClient(OpenAIClient):
    def __init__(
        self,
        api_key: str,
        model_id: str,
        api_base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        base_url = api_base_url or "http://localhost:1234/v1"
        super().__init__(
            api_key=api_key or "not-needed",
            model_id=model_id,
            api_base_url=base_url,
            transport=transport,
        )


def create_llm_client(model_config) -> BaseLLMClient:
    """Factory function that returns the appropriate LLM client based on provider."""
    provider = model_config.provider.lower()
    if provider == "openai":
        return OpenAIClient(
            api_key=model_config.api_key,
            model_id=model_config.model_id,
            api_base_url=model_config.api_base_url,
        )
    elif provider == "anthropic":
        return AnthropicClient(
            api_key=model_config.api_key,
            model_id=model_config.model_id,
            api_base_url=model_config.api_base_url,
        )
    elif provider == "local":
        return LocalClient(
            api_key=model_config.api_key,
            model_id=model_config.model_id,
            api_base_url=model_config.api_base_url,
        )
    else:
        raise ValueError(f"Unknown provider: {model_config.provider}")
