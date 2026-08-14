import asyncio
import os
import tempfile

# Point the app at a throwaway database BEFORE any app module is imported —
# app.config and app.database read settings at import time.
_TEST_DB_DIR = tempfile.mkdtemp(prefix="agent_eval_test_")
os.environ["AGENT_EVAL_DATABASE_URL"] = f"sqlite:///{_TEST_DB_DIR}/test.db"
os.environ["AGENT_EVAL_LLM_MAX_RETRIES"] = "2"
os.environ["AGENT_EVAL_CODE_EXEC_TIMEOUT_SECONDS"] = "2"

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.database import Base, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import dispatcher  # noqa: E402
from app.services.llm_clients import LLMResponse  # noqa: E402


@pytest.fixture(autouse=True)
async def clean_db():
    """Fresh schema per test; also reset loop-bound dispatcher state, since
    pytest-asyncio gives every test its own event loop."""
    dispatcher._global_semaphore = None
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await init_db()
    yield
    # Let stray executor tasks finish so they don't outlive the test loop.
    pending = [t for t in dispatcher._background_tasks if not t.done()]
    if pending:
        await asyncio.wait(pending, timeout=15)


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class FakeLLMClient:
    """Deterministic in-process replacement for provider clients."""

    def __init__(self, responder=None, chat_responder=None, delay: float = 0.0):
        self.responder = responder or (lambda prompt: "42")
        # chat_responder(messages) -> text; used by multi-turn agent loops
        self.chat_responder = chat_responder
        self.delay = delay
        self.calls: list[tuple[str, dict]] = []
        self.chat_calls: list[tuple[list, dict]] = []
        self.closed = False

    async def complete(self, prompt: str, params: dict | None = None) -> LLMResponse:
        self.calls.append((prompt, dict(params or {})))
        if self.delay:
            await asyncio.sleep(self.delay)
        text = self.responder(prompt)
        if isinstance(text, Exception):
            raise text
        return LLMResponse(text=text, latency_ms=7, input_tokens=10, output_tokens=5)

    async def chat(self, messages: list, params: dict | None = None) -> LLMResponse:
        if self.chat_responder is None:
            prompt = next(
                m["content"] for m in reversed(messages) if m["role"] == "user"
            )
            return await self.complete(prompt, params)
        self.chat_calls.append(([dict(m) for m in messages], dict(params or {})))
        if self.delay:
            await asyncio.sleep(self.delay)
        text = self.chat_responder(messages)
        if isinstance(text, Exception):
            raise text
        return LLMResponse(text=text, latency_ms=7, input_tokens=10, output_tokens=5)

    async def aclose(self) -> None:
        self.closed = True


@pytest.fixture
def fake_llm(monkeypatch):
    """Patch the dispatcher's client factory; tests configure fake.responder."""
    fake = FakeLLMClient()
    monkeypatch.setattr(dispatcher, "create_llm_client", lambda model_config: fake)
    return fake


async def wait_until(predicate, timeout: float = 10.0, interval: float = 0.05):
    """Poll an async predicate until truthy or time out."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        result = await predicate()
        if result:
            return result
        if loop.time() > deadline:
            raise TimeoutError("condition not met within timeout")
        await asyncio.sleep(interval)
