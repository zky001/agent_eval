import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx


@dataclass
class LLMResponse:
    text: str
    latency_ms: int
    input_tokens: int
    output_tokens: int


class BaseLLMClient(ABC):
    @abstractmethod
    async def complete(self, prompt: str, params: dict | None = None) -> LLMResponse:
        pass


class OpenAIClient(BaseLLMClient):
    def __init__(self, api_key: str, model_id: str, api_base_url: str | None = None):
        self.api_key = api_key
        self.model_id = model_id
        self.api_base_url = (api_base_url or "https://api.openai.com/v1").rstrip("/")

    async def complete(self, prompt: str, params: dict | None = None) -> LLMResponse:
        params = params or {}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            **params,
        }

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.api_base_url}/chat/completions",
                headers=headers,
                json=body,
            )
            response.raise_for_status()

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        data = response.json()

        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResponse(
            text=choice,
            latency_ms=elapsed_ms,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )


class AnthropicClient(BaseLLMClient):
    def __init__(self, api_key: str, model_id: str):
        self.api_key = api_key
        self.model_id = model_id
        self.api_base_url = "https://api.anthropic.com/v1"

    async def complete(self, prompt: str, params: dict | None = None) -> LLMResponse:
        params = params or {}
        max_tokens = params.pop("max_tokens", 4096)
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model_id,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            **params,
        }

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.api_base_url}/messages",
                headers=headers,
                json=body,
            )
            response.raise_for_status()

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        data = response.json()

        text = data["content"][0]["text"]
        usage = data.get("usage", {})
        return LLMResponse(
            text=text,
            latency_ms=elapsed_ms,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )


class LocalClient(OpenAIClient):
    def __init__(self, api_key: str, model_id: str, api_base_url: str | None = None):
        base_url = api_base_url or "http://localhost:1234/v1"
        super().__init__(api_key=api_key or "not-needed", model_id=model_id, api_base_url=base_url)


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
        )
    elif provider == "local":
        return LocalClient(
            api_key=model_config.api_key,
            model_id=model_config.model_id,
            api_base_url=model_config.api_base_url,
        )
    else:
        raise ValueError(f"Unknown provider: {model_config.provider}")
