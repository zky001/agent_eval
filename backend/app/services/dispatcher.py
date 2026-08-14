import asyncio
import json
import logging
import re

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import settings
from app.evaluation.registry import EvaluatorRegistry
from app.models.dataset import Dataset, DatasetItem
from app.models.evaluation_run import EvaluationRun
from app.models.model_config import ModelConfig
from app.models.result import Result
from app.models.task import Task
from app.services.agent_loop import run_agent_loop
from app.services.llm_clients import create_llm_client
from app.utils import utcnow

logger = logging.getLogger(__name__)

# One semaphore for the whole process so MAX_CONCURRENT_TASKS bounds LLM
# concurrency globally. The previous per-run semaphore meant N parallel runs
# produced N x 10 in-flight requests and exhausted the DB connection pool.
_global_semaphore: asyncio.Semaphore | None = None

# asyncio.create_task results must be referenced or the task can be garbage
# collected mid-flight; executors register here until they finish.
_background_tasks: set[asyncio.Task] = set()

JUDGE_PROMPT_TEMPLATE = """You are an impartial evaluation judge. Grade the candidate response below.

# Task given to the model
{question}

# Rubric / reference answer
{reference}

# Candidate response
{response}

Grade the candidate response against the rubric on a scale from 0.0 (completely fails) to 1.0 (fully satisfies).
Respond with ONLY a JSON object in exactly this form:
{{"score": <float between 0.0 and 1.0>, "reasoning": "<one short paragraph explaining the grade>"}}"""


def _get_semaphore() -> asyncio.Semaphore:
    global _global_semaphore
    if _global_semaphore is None:
        _global_semaphore = asyncio.Semaphore(max(1, settings.MAX_CONCURRENT_TASKS))
    return _global_semaphore


def spawn_run(db_session_factory: async_sessionmaker, run_id: int) -> asyncio.Task:
    """Start a RunExecutor in the background, keeping a strong reference."""
    executor = RunExecutor(db_session_factory, run_id)
    task = asyncio.create_task(executor.execute(), name=f"run-{run_id}")
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


def _parse_json_dict(value) -> dict:
    if not value:
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return value


def parse_judge_response(text: str) -> tuple[float, str]:
    """Extract (score, reasoning) from a judge model's response.

    Tolerates surrounding prose or code fences; falls back to a bare-number
    scan so a partially-formatted verdict still yields a usable score."""
    for candidate in re.findall(r"\{.*?\}", text, re.DOTALL):
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict) and "score" in parsed:
            try:
                score = float(parsed["score"])
            except (TypeError, ValueError):
                continue
            reasoning = str(parsed.get("reasoning", "")).strip()
            return max(0.0, min(1.0, score)), reasoning

    match = re.search(r"score\s*[:=]\s*([01](?:\.\d+)?|\.\d+)", text, re.IGNORECASE)
    if match:
        return max(0.0, min(1.0, float(match.group(1)))), text.strip()[:500]

    raise ValueError(f"Could not parse judge verdict from: {text[:200]!r}")


class RunExecutor:
    def __init__(self, db_session_factory: async_sessionmaker, run_id: int):
        self.db_session_factory = db_session_factory
        self.run_id = run_id

    async def execute(self) -> None:
        llm_client = None
        judge_client = None
        try:
            run = await self._wait_for_run()
            if run is None:
                logger.error(f"Run {self.run_id} not found")
                return
            if run.status == "cancelled":
                return

            async with self.db_session_factory() as db:
                run = await db.get(EvaluationRun, self.run_id)

                dataset = await db.get(Dataset, run.dataset_id)
                if dataset is None:
                    await self._fail_run(db, run, f"Dataset {run.dataset_id} not found")
                    return

                model_config = await db.get(ModelConfig, run.model_config_id)
                if model_config is None:
                    await self._fail_run(
                        db, run, f"Model config {run.model_config_id} not found"
                    )
                    return

                judge_config = None
                if run.judge_model_config_id:
                    judge_config = await db.get(
                        ModelConfig, run.judge_model_config_id
                    )
                    if judge_config is None:
                        await self._fail_run(
                            db,
                            run,
                            f"Judge model config {run.judge_model_config_id} not found",
                        )
                        return

                # Resume support: a retried run already has its tasks — only
                # the ones reset to "pending" need processing.
                existing_tasks = (
                    (
                        await db.execute(
                            select(Task).where(Task.run_id == self.run_id)
                        )
                    )
                    .scalars()
                    .all()
                )

                if existing_tasks:
                    tasks = existing_tasks
                    pending_pairs = [
                        (t.id, t.dataset_item_id)
                        for t in tasks
                        if t.status == "pending"
                    ]
                else:
                    items_result = await db.execute(
                        select(DatasetItem)
                        .where(DatasetItem.dataset_id == dataset.id)
                        .order_by(DatasetItem.item_index)
                    )
                    dataset_items = items_result.scalars().all()
                    if not dataset_items:
                        await self._fail_run(db, run, "Dataset has no items")
                        return
                    tasks = [
                        Task(
                            run_id=self.run_id,
                            dataset_item_id=item.id,
                            status="pending",
                        )
                        for item in dataset_items
                    ]
                    db.add_all(tasks)
                    # flush assigns primary keys before we read them
                    await db.flush()
                    pending_pairs = [(t.id, t.dataset_item_id) for t in tasks]

                run.status = "running"
                run.total_tasks = len(tasks)
                run.started_at = utcnow()

                merged_params = {
                    **_parse_json_dict(model_config.default_params),
                    **_parse_json_dict(run.params_override),
                }
                # Dataset-level system prompt, unless the run overrides it
                dataset_meta = _parse_json_dict(dataset.metadata_)
                if dataset_meta.get("system_prompt") and "system" not in merged_params:
                    merged_params["system"] = dataset_meta["system_prompt"]

                dataset_type = dataset.dataset_type
                await db.commit()

            llm_client = create_llm_client(model_config)
            if judge_config is not None:
                judge_client = create_llm_client(judge_config)
            semaphore = _get_semaphore()

            async def process_task(task_id: int, dataset_item_id: int) -> None:
                async with semaphore:
                    await self._process_single_task(
                        task_id, dataset_item_id, llm_client, merged_params, dataset_type
                    )

            results = await asyncio.gather(
                *[
                    process_task(task_id, item_id)
                    for task_id, item_id in pending_pairs
                ],
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, BaseException):
                    logger.error(f"Run {self.run_id} task raised: {r!r}")

            await self._evaluate_results(dataset_type, judge_client)

        except Exception as e:
            logger.exception(f"Run {self.run_id} failed with error: {e}")
            try:
                async with self.db_session_factory() as db:
                    run = await db.get(EvaluationRun, self.run_id)
                    if run:
                        run.status = "failed"
                        run.error_message = str(e)
                        run.completed_at = utcnow()
                        await db.commit()
            except Exception:
                logger.exception("Failed to update run status after error")
        finally:
            if llm_client is not None:
                await llm_client.aclose()
            if judge_client is not None:
                await judge_client.aclose()

    async def _wait_for_run(self) -> EvaluationRun | None:
        """Fetch the run, tolerating a spawn that raced the creating commit."""
        for attempt in range(5):
            async with self.db_session_factory() as db:
                run = await db.get(EvaluationRun, self.run_id)
                if run is not None:
                    return run
            await asyncio.sleep(0.1 * (attempt + 1))
        return None

    async def _fail_run(self, db, run: EvaluationRun, message: str) -> None:
        run.status = "failed"
        run.error_message = message
        run.completed_at = utcnow()
        await db.commit()

    async def _is_cancelled(self) -> bool:
        async with self.db_session_factory() as db:
            status = (
                await db.execute(
                    select(EvaluationRun.status).where(EvaluationRun.id == self.run_id)
                )
            ).scalar_one_or_none()
            return status == "cancelled"

    async def _process_single_task(
        self,
        task_id: int,
        dataset_item_id: int,
        llm_client,
        params: dict,
        dataset_type: str,
    ) -> None:
        # Short session: mark the task running. The session is closed before
        # the LLM call so slow requests don't pin DB connections.
        if await self._is_cancelled():
            return

        async with self.db_session_factory() as db:
            task = await db.get(Task, task_id)
            dataset_item = await db.get(DatasetItem, dataset_item_id)
            if not task or not dataset_item:
                return
            prompt = dataset_item.prompt
            item_meta = _parse_json_dict(dataset_item.metadata_)
            task.status = "running"
            task.dispatched_at = utcnow()
            await db.commit()

        # Item-level system prompt beats the dataset-level one
        if item_meta.get("system_prompt"):
            params = {**params, "system": item_meta["system_prompt"]}

        error: Exception | None = None
        raw_response: str | None = None
        trajectory_json: str | None = None
        latency_ms = 0
        input_tokens = 0
        output_tokens = 0
        try:
            if dataset_type == "agent_loop":
                outcome = await run_agent_loop(llm_client, prompt, item_meta, params)
                raw_response = outcome.final_answer or outcome.last_output
                trajectory_json = json.dumps(outcome.trajectory)
                latency_ms = outcome.latency_ms
                input_tokens = outcome.input_tokens
                output_tokens = outcome.output_tokens
            else:
                llm_response = await llm_client.complete(prompt, params)
                raw_response = llm_response.text
                latency_ms = llm_response.latency_ms
                input_tokens = llm_response.input_tokens
                output_tokens = llm_response.output_tokens
        except Exception as e:
            error = e
            logger.error(f"Task {task_id} failed: {e}")

        # Second short session: persist the outcome.
        async with self.db_session_factory() as db:
            task = await db.get(Task, task_id)
            if task is None:
                return
            task.completed_at = utcnow()

            if error is None:
                task.status = "completed"
                db.add(
                    Result(
                        task_id=task_id,
                        raw_response=raw_response,
                        trajectory=trajectory_json,
                        latency_ms=latency_ms,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        token_count=input_tokens + output_tokens,
                    )
                )
                counter = {"completed_tasks": EvaluationRun.completed_tasks + 1}
            else:
                task.status = "failed"
                db.add(
                    Result(
                        task_id=task_id,
                        raw_response=None,
                        evaluation_details=json.dumps({"error": str(error)}),
                    )
                )
                counter = {"failed_tasks": EvaluationRun.failed_tasks + 1}

            # Atomic increment; read-modify-write raced between tasks.
            await db.execute(
                update(EvaluationRun)
                .where(EvaluationRun.id == self.run_id)
                .values(**counter)
            )
            await db.commit()

    async def _judge_rows(self, rows, judge_client) -> None:
        """Score each completed result with the judge model, concurrently.

        Only the LLM calls run concurrently; ORM attributes are written
        sequentially afterwards because sessions are not concurrency-safe.
        """
        semaphore = _get_semaphore()

        async def judge_one(result, dataset_item):
            prompt = JUDGE_PROMPT_TEMPLATE.format(
                question=dataset_item.prompt,
                reference=dataset_item.reference_answer or "(no rubric provided)",
                response=result.raw_response,
            )
            async with semaphore:
                verdict = await judge_client.complete(prompt, {"max_tokens": 1024})
            return parse_judge_response(verdict.text)

        outcomes = await asyncio.gather(
            *[judge_one(result, item) for _, result, item in rows],
            return_exceptions=True,
        )

        for (task, result, dataset_item), outcome in zip(rows, outcomes):
            result.parsed_answer = (result.raw_response or "").strip()
            if isinstance(outcome, BaseException):
                logger.error(f"Judge failed for task {task.id}: {outcome!r}")
                result.is_correct = False
                result.score = 0.0
                result.evaluation_details = json.dumps(
                    {"error": f"Judge scoring failed: {outcome}"}
                )
                continue
            score, reasoning = outcome
            item_meta = _parse_json_dict(dataset_item.metadata_)
            threshold = float(item_meta.get("pass_threshold", 0.7))
            result.score = score
            result.is_correct = score >= threshold
            result.evaluation_details = json.dumps(
                {
                    "judge_score": score,
                    "judge_reasoning": reasoning,
                    "pass_threshold": threshold,
                }
            )

    async def _evaluate_results(self, dataset_type: str, judge_client=None) -> None:
        async with self.db_session_factory() as db:
            rows = (
                await db.execute(
                    select(Task, Result, DatasetItem)
                    .join(Result, Result.task_id == Task.id)
                    .join(DatasetItem, DatasetItem.id == Task.dataset_item_id)
                    .where(Task.run_id == self.run_id)
                    .where(Task.status == "completed")
                    .where(Result.raw_response.isnot(None))
                )
            ).all()

            if judge_client is not None:
                await self._judge_rows(rows, judge_client)
            else:
                evaluator = EvaluatorRegistry.get(dataset_type)
                for task, result, dataset_item in rows:
                    item_metadata = _parse_json_dict(dataset_item.metadata_)
                    if dataset_type == "agent_loop":
                        try:
                            item_metadata["_trajectory"] = json.loads(
                                result.trajectory or "[]"
                            )
                        except (json.JSONDecodeError, TypeError):
                            item_metadata["_trajectory"] = []

                    # Evaluators are synchronous and may run subprocesses
                    # (humaneval); keep them off the event loop.
                    parsed = await asyncio.to_thread(
                        evaluator.parse_answer, result.raw_response, item_metadata
                    )
                    result.parsed_answer = parsed

                    if dataset_item.reference_answer:
                        try:
                            eval_result = await asyncio.to_thread(
                                evaluator.score,
                                parsed,
                                dataset_item.reference_answer,
                                item_metadata,
                            )
                        except Exception as e:
                            logger.exception(
                                f"Scoring failed for task {task.id} in run {self.run_id}"
                            )
                            result.is_correct = False
                            result.score = 0.0
                            result.evaluation_details = json.dumps(
                                {"error": f"Evaluator raised: {e}"}
                            )
                            continue

                        result.is_correct = eval_result.is_correct
                        result.score = eval_result.score
                        result.evaluation_details = json.dumps(eval_result.details)

            total_score = 0.0
            scored_count = 0
            for _, result, _ in rows:
                if result.score is not None:
                    total_score += result.score
                    scored_count += 1

            run = await db.get(EvaluationRun, self.run_id)
            if run:
                cancelled = run.status == "cancelled"
                if scored_count > 0:
                    run.aggregate_score = total_score / scored_count

                if cancelled:
                    # Keep the cancelled status (previously it was clobbered
                    # to "completed") and close out tasks that never ran.
                    await db.execute(
                        update(Task)
                        .where(Task.run_id == self.run_id)
                        .where(Task.status.in_(["pending", "running"]))
                        .values(status="cancelled", completed_at=utcnow())
                    )
                elif run.total_tasks > 0 and run.completed_tasks == 0:
                    run.status = "failed"
                    run.error_message = (
                        run.error_message
                        or "All tasks failed - check the model configuration and API key"
                    )
                else:
                    run.status = "completed"

                run.completed_at = utcnow()

            await db.commit()
