"""Import real benchmark data through the HuggingFace datasets-server API.

Uses the public REST endpoint (https://datasets-server.huggingface.co/rows)
so no HF SDK, token, or dataset download is required.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

HF_ROWS_URL = "https://datasets-server.huggingface.co/rows"
PAGE_SIZE = 100  # server-side maximum
DEFAULT_MAX_ITEMS = 50
HARD_MAX_ITEMS = 500

HF_SOURCES = {
    "gsm8k": {"dataset": "openai/gsm8k", "config": "main", "split": "test"},
    "mmlu": {"dataset": "cais/mmlu", "config": "all", "split": "test"},
    "humaneval": {
        "dataset": "openai/openai_humaneval",
        "config": "openai_humaneval",
        "split": "test",
    },
}


class HFImportError(RuntimeError):
    pass


def _map_gsm8k(row: dict) -> dict:
    return {
        "prompt": (
            row["question"]
            + "\n\nEnd your response with the final numeric answer in the form: #### <number>"
        ),
        "reference_answer": row["answer"],
    }


def _map_mmlu(row: dict) -> dict:
    letters = ["A", "B", "C", "D"]
    choices = "\n".join(
        f"{letters[i]}) {choice}" for i, choice in enumerate(row["choices"][:4])
    )
    return {
        "prompt": (
            f"{row['question']}\n{choices}"
            "\n\nRespond with the letter of the correct option in the form: Answer: <letter>"
        ),
        "reference_answer": letters[int(row["answer"])],
        "metadata": {"subject": row.get("subject", "")},
    }


def _map_humaneval(row: dict) -> dict:
    return {
        "prompt": (
            "Complete the following Python function. Return the COMPLETE "
            "implementation (including the signature) in a ```python code block.\n\n"
            f"```python\n{row['prompt']}\n```"
        ),
        "reference_answer": row["prompt"] + row.get("canonical_solution", ""),
        "metadata": {
            "test_cases": f"{row['test']}\n\ncheck({row['entry_point']})",
            "task_id": row.get("task_id", ""),
        },
    }


_ROW_MAPPERS = {
    "gsm8k": _map_gsm8k,
    "mmlu": _map_mmlu,
    "humaneval": _map_humaneval,
}


async def fetch_hf_samples(source: str, max_items: int | None = None) -> list[dict]:
    """Fetch up to max_items rows for a known source, mapped to item dicts."""
    if source not in HF_SOURCES:
        raise HFImportError(
            f"HuggingFace import is not available for '{source}'. "
            f"Available: {sorted(HF_SOURCES)}"
        )

    target = min(max_items or DEFAULT_MAX_ITEMS, HARD_MAX_ITEMS)
    cfg = HF_SOURCES[source]
    mapper = _ROW_MAPPERS[source]
    samples: list[dict] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        offset = 0
        while len(samples) < target:
            length = min(PAGE_SIZE, target - len(samples))
            try:
                response = await client.get(
                    HF_ROWS_URL,
                    params={
                        "dataset": cfg["dataset"],
                        "config": cfg["config"],
                        "split": cfg["split"],
                        "offset": offset,
                        "length": length,
                    },
                )
            except (httpx.TimeoutException, httpx.TransportError) as e:
                raise HFImportError(
                    f"Could not reach HuggingFace datasets-server: {e}"
                ) from e
            if response.status_code != 200:
                raise HFImportError(
                    f"HuggingFace datasets-server returned HTTP "
                    f"{response.status_code}: {response.text[:300]}"
                )

            rows = response.json().get("rows", [])
            if not rows:
                break
            for entry in rows:
                try:
                    samples.append(mapper(entry["row"]))
                except (KeyError, IndexError, TypeError, ValueError) as e:
                    logger.warning(f"Skipping malformed HF row for {source}: {e}")
            offset += len(rows)

    if not samples:
        raise HFImportError(f"HuggingFace returned no rows for '{source}'")
    return samples
