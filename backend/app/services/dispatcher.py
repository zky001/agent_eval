import asyncio
import json
import logging
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.evaluation.registry import EvaluatorRegistry
from app.models.dataset import Dataset, DatasetItem
from app.models.evaluation_run import EvaluationRun
from app.models.model_config import ModelConfig
from app.models.result import Result
from app.models.task import Task
from app.services.llm_clients import create_llm_client

logger = logging.getLogger(__name__)


class RunExecutor:
    def __init__(self, db_session_factory: async_sessionmaker, run_id: int):
        self.db_session_factory = db_session_factory
        self.run_id = run_id

    async def execute(self) -> None:
        try:
            async with self.db_session_factory() as db:
                # Load the run
                run = await db.get(EvaluationRun, self.run_id)
                if run is None:
                    logger.error(f"Run {self.run_id} not found")
                    return

                if run.status == "cancelled":
                    return

                # Load dataset and items
                dataset = await db.get(Dataset, run.dataset_id)
                if dataset is None:
                    run.status = "failed"
                    run.error_message = f"Dataset {run.dataset_id} not found"
                    await db.commit()
                    return

                items_result = await db.execute(
                    select(DatasetItem)
                    .where(DatasetItem.dataset_id == dataset.id)
                    .order_by(DatasetItem.item_index)
                )
                dataset_items = items_result.scalars().all()

                if not dataset_items:
                    run.status = "failed"
                    run.error_message = "Dataset has no items"
                    await db.commit()
                    return

                # Load model config
                model_config = await db.get(ModelConfig, run.model_config_id)
                if model_config is None:
                    run.status = "failed"
                    run.error_message = f"Model config {run.model_config_id} not found"
                    await db.commit()
                    return

                # Create tasks for each dataset item
                tasks = []
                for item in dataset_items:
                    task = Task(
                        run_id=self.run_id,
                        dataset_item_id=item.id,
                        status="pending",
                    )
                    db.add(task)
                    tasks.append(task)

                # Update run
                run.status = "running"
                run.total_tasks = len(tasks)
                run.started_at = datetime.utcnow()
                await db.commit()

                # Refresh to get IDs
                for task in tasks:
                    await db.refresh(task)

                # Store IDs for later use (we'll re-query in separate sessions)
                task_item_pairs = [
                    (task.id, task.dataset_item_id) for task in tasks
                ]

            # Create LLM client
            async with self.db_session_factory() as db:
                model_config = await db.get(ModelConfig, run.model_config_id)
                run = await db.get(EvaluationRun, self.run_id)
                params_override = {}
                if run.params_override:
                    if isinstance(run.params_override, str):
                        params_override = json.loads(run.params_override)
                    else:
                        params_override = run.params_override

            llm_client = create_llm_client(model_config)

            # Get default params
            default_params = {}
            if model_config.default_params:
                if isinstance(model_config.default_params, str):
                    default_params = json.loads(model_config.default_params)
                else:
                    default_params = model_config.default_params

            merged_params = {**default_params, **params_override}

            # Dispatch tasks with bounded concurrency
            semaphore = asyncio.Semaphore(10)

            async def process_task(task_id: int, dataset_item_id: int) -> None:
                async with semaphore:
                    await self._process_single_task(
                        task_id, dataset_item_id, llm_client, merged_params
                    )

            await asyncio.gather(
                *[
                    process_task(task_id, item_id)
                    for task_id, item_id in task_item_pairs
                ],
                return_exceptions=True,
            )

            # Run evaluator on all results and compute aggregate
            await self._evaluate_results(dataset.dataset_type)

        except Exception as e:
            logger.exception(f"Run {self.run_id} failed with error: {e}")
            try:
                async with self.db_session_factory() as db:
                    run = await db.get(EvaluationRun, self.run_id)
                    if run:
                        run.status = "failed"
                        run.error_message = str(e)
                        run.completed_at = datetime.utcnow()
                        await db.commit()
            except Exception:
                logger.exception("Failed to update run status after error")

    async def _process_single_task(
        self,
        task_id: int,
        dataset_item_id: int,
        llm_client,
        params: dict,
    ) -> None:
        async with self.db_session_factory() as db:
            # Check if run is cancelled
            run = await db.get(EvaluationRun, self.run_id)
            if run and run.status == "cancelled":
                return

            task = await db.get(Task, task_id)
            dataset_item = await db.get(DatasetItem, dataset_item_id)

            if not task or not dataset_item:
                return

            task.status = "running"
            task.dispatched_at = datetime.utcnow()
            await db.commit()

            try:
                llm_response = await llm_client.complete(dataset_item.prompt, params)

                result = Result(
                    task_id=task_id,
                    raw_response=llm_response.text,
                    latency_ms=llm_response.latency_ms,
                    token_count=llm_response.input_tokens + llm_response.output_tokens,
                )
                db.add(result)

                task.status = "completed"
                task.completed_at = datetime.utcnow()

                # Update run progress
                run = await db.get(EvaluationRun, self.run_id)
                if run:
                    run.completed_tasks = (run.completed_tasks or 0) + 1

                await db.commit()

            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}")
                task.status = "failed"
                task.completed_at = datetime.utcnow()

                result = Result(
                    task_id=task_id,
                    raw_response=None,
                    evaluation_details=json.dumps({"error": str(e)}),
                )
                db.add(result)

                run = await db.get(EvaluationRun, self.run_id)
                if run:
                    run.failed_tasks = (run.failed_tasks or 0) + 1

                await db.commit()

    async def _evaluate_results(self, dataset_type: str) -> None:
        evaluator = EvaluatorRegistry.get(dataset_type)

        async with self.db_session_factory() as db:
            # Get all tasks with results for this run
            tasks_result = await db.execute(
                select(Task).where(Task.run_id == self.run_id)
            )
            tasks = tasks_result.scalars().all()

            total_score = 0.0
            scored_count = 0

            for task in tasks:
                if task.status != "completed":
                    continue

                # Load result
                result_query = await db.execute(
                    select(Result).where(Result.task_id == task.id)
                )
                result = result_query.scalar_one_or_none()

                if not result or not result.raw_response:
                    continue

                # Load dataset item for reference answer
                dataset_item = await db.get(DatasetItem, task.dataset_item_id)
                if not dataset_item:
                    continue

                item_metadata = {}
                if dataset_item.metadata_:
                    if isinstance(dataset_item.metadata_, str):
                        try:
                            item_metadata = json.loads(dataset_item.metadata_)
                        except (json.JSONDecodeError, TypeError):
                            item_metadata = {}
                    else:
                        item_metadata = dataset_item.metadata_

                # Parse and score
                parsed = evaluator.parse_answer(result.raw_response, item_metadata)
                result.parsed_answer = parsed

                if dataset_item.reference_answer:
                    eval_result = evaluator.score(
                        parsed, dataset_item.reference_answer, item_metadata
                    )
                    result.is_correct = eval_result.is_correct
                    result.score = eval_result.score
                    result.evaluation_details = json.dumps(eval_result.details)

                    total_score += eval_result.score
                    scored_count += 1

            # Update run with aggregate score
            run = await db.get(EvaluationRun, self.run_id)
            if run:
                if scored_count > 0:
                    run.aggregate_score = total_score / scored_count
                else:
                    run.aggregate_score = 0.0
                run.status = "completed"
                run.completed_at = datetime.utcnow()

            await db.commit()
