"""Round-2 feature tests: retry, export, comparison, system prompts, judge."""

import pytest

from app.services import dispatcher
from app.services.dispatcher import parse_judge_response
from tests.conftest import FakeLLMClient
from tests.test_api import create_test_model, import_dataset, wait_for_run_terminal


class TestJudgeVerdictParsing:
    def test_plain_json(self):
        score, reasoning = parse_judge_response('{"score": 0.8, "reasoning": "solid"}')
        assert score == 0.8
        assert reasoning == "solid"

    def test_json_with_surrounding_prose(self):
        text = 'Here is my verdict:\n```json\n{"score": 0.5, "reasoning": "partial"}\n```\nDone.'
        score, reasoning = parse_judge_response(text)
        assert score == 0.5

    def test_score_clamped(self):
        score, _ = parse_judge_response('{"score": 1.7, "reasoning": "x"}')
        assert score == 1.0

    def test_score_line_fallback(self):
        score, _ = parse_judge_response("I would give this a score: 0.75 overall.")
        assert score == 0.75

    def test_unparseable_raises(self):
        with pytest.raises(ValueError):
            parse_judge_response("no verdict here")


class TestRetry:
    async def test_retry_reruns_failed_tasks(self, client, fake_llm):
        fake_llm.responder = lambda prompt: RuntimeError("boom")
        model = await create_test_model(client)
        ds = await import_dataset(client, "gsm8k", max_items=2)
        run = (
            await client.post(
                "/api/runs/",
                json={"dataset_id": ds["id"], "model_config_id": model["id"]},
            )
        ).json()
        final = await wait_for_run_terminal(client, run["id"])
        assert final["status"] == "failed"
        assert final["failed_tasks"] == 2

        # The provider recovers; retry only the failed tasks
        fake_llm.responder = lambda prompt: "#### 18" if "Janet" in prompt else "#### 3"
        resp = await client.post(f"/api/runs/{run['id']}/retry")
        assert resp.status_code == 200, resp.text

        final = await wait_for_run_terminal(client, run["id"])
        assert final["status"] == "completed"
        assert final["failed_tasks"] == 0
        assert final["completed_tasks"] == 2
        assert final["aggregate_score"] == 1.0

    async def test_retry_rejected_when_nothing_to_retry(self, client, fake_llm):
        fake_llm.responder = lambda prompt: "#### 18"
        model = await create_test_model(client)
        ds = await import_dataset(client, "gsm8k", max_items=1)
        run = (
            await client.post(
                "/api/runs/",
                json={"dataset_id": ds["id"], "model_config_id": model["id"]},
            )
        ).json()
        await wait_for_run_terminal(client, run["id"])
        resp = await client.post(f"/api/runs/{run['id']}/retry")
        assert resp.status_code == 400


class TestExport:
    async def test_export_csv(self, client, fake_llm):
        fake_llm.responder = lambda prompt: "#### 18"
        model = await create_test_model(client)
        ds = await import_dataset(client, "gsm8k", max_items=1)
        run = (
            await client.post(
                "/api/runs/",
                json={"dataset_id": ds["id"], "model_config_id": model["id"]},
            )
        ).json()
        await wait_for_run_terminal(client, run["id"])

        resp = await client.get(f"/api/runs/{run['id']}/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "attachment" in resp.headers["content-disposition"]
        lines = resp.text.strip().splitlines()
        assert lines[0].startswith("item_index,prompt,reference_answer")
        assert len(lines) >= 2
        assert "#### 18" in resp.text


class TestCompareItems:
    async def test_compare_two_runs(self, client, fake_llm):
        model_a = await create_test_model(client, name="model-a")
        model_b = await create_test_model(client, name="model-b")
        ds = await import_dataset(client, "gsm8k", max_items=2)

        fake_llm.responder = lambda prompt: "#### 18" if "Janet" in prompt else "#### 999"
        run_ids = []
        for model in (model_a, model_b):
            run = (
                await client.post(
                    "/api/runs/",
                    json={"dataset_id": ds["id"], "model_config_id": model["id"]},
                )
            ).json()
            await wait_for_run_terminal(client, run["id"])
            run_ids.append(run["id"])

        resp = await client.get(
            "/api/runs/compare-items",
            params={"run_ids": f"{run_ids[0]},{run_ids[1]}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert [r["id"] for r in data["runs"]] == run_ids
        assert len(data["items"]) == 2
        first = data["items"][0]
        assert first["item_index"] == 0
        assert set(first["results"].keys()) == {str(run_ids[0]), str(run_ids[1])}
        assert first["results"][str(run_ids[0])]["raw_response"] == "#### 18"

    async def test_compare_requires_same_dataset(self, client, fake_llm):
        fake_llm.responder = lambda prompt: "#### 1"
        model = await create_test_model(client)
        ds_a = await import_dataset(client, "gsm8k", max_items=1)
        ds_b = await import_dataset(client, "mmlu", max_items=1)
        ids = []
        for ds in (ds_a, ds_b):
            run = (
                await client.post(
                    "/api/runs/",
                    json={"dataset_id": ds["id"], "model_config_id": model["id"]},
                )
            ).json()
            await wait_for_run_terminal(client, run["id"])
            ids.append(run["id"])

        resp = await client.get(
            "/api/runs/compare-items", params={"run_ids": f"{ids[0]},{ids[1]}"}
        )
        assert resp.status_code == 400

    async def test_compare_missing_run_404(self, client, fake_llm):
        resp = await client.get(
            "/api/runs/compare-items", params={"run_ids": "998,999"}
        )
        assert resp.status_code == 404


class TestSystemPrompt:
    async def test_dataset_system_prompt_reaches_llm(self, client, fake_llm):
        fake_llm.responder = lambda prompt: "ok"
        model = await create_test_model(client)
        resp = await client.post(
            "/api/datasets/upload",
            json={
                "name": "with-system",
                "dataset_type": "custom",
                "system_prompt": "You are terse.",
                "items": [{"prompt": "Say ok", "reference_answer": "ok"}],
            },
        )
        ds = resp.json()
        run = (
            await client.post(
                "/api/runs/",
                json={"dataset_id": ds["id"], "model_config_id": model["id"]},
            )
        ).json()
        await wait_for_run_terminal(client, run["id"])
        assert fake_llm.calls
        _, params = fake_llm.calls[0]
        assert params.get("system") == "You are terse."


class TestLLMJudge:
    async def test_judge_run_scores_with_judge_model(self, client, monkeypatch):
        candidate = FakeLLMClient(
            responder=lambda p: "An API is like a waiter taking your order."
        )
        judge = FakeLLMClient(
            responder=lambda p: '{"score": 0.85, "reasoning": "clear, accurate analogy"}'
        )

        def factory(model_config):
            return judge if model_config.name == "judge-model" else candidate

        monkeypatch.setattr(dispatcher, "create_llm_client", factory)

        model = await create_test_model(client, name="candidate-model")
        judge_model = await create_test_model(client, name="judge-model")
        ds = await import_dataset(client, "llm_judge", max_items=2)

        run = (
            await client.post(
                "/api/runs/",
                json={
                    "dataset_id": ds["id"],
                    "model_config_id": model["id"],
                    "judge_model_config_id": judge_model["id"],
                },
            )
        ).json()
        assert run["judge_model_config_id"] == judge_model["id"]

        final = await wait_for_run_terminal(client, run["id"])
        assert final["status"] == "completed"
        assert abs(final["aggregate_score"] - 0.85) < 1e-6

        # The judge saw the candidate's answer inside its grading prompt
        assert len(judge.calls) == 2
        assert "waiter taking your order" in judge.calls[0][0]

        tasks = (await client.get(f"/api/runs/{run['id']}/tasks")).json()
        first = tasks["tasks"][0]
        assert first["is_correct"] is True  # 0.85 >= 0.7 threshold
        assert first["evaluation_details"]["judge_reasoning"] == "clear, accurate analogy"

    async def test_judge_dataset_requires_judge_model(self, client, fake_llm):
        model = await create_test_model(client)
        ds = await import_dataset(client, "llm_judge", max_items=1)
        resp = await client.post(
            "/api/runs/",
            json={"dataset_id": ds["id"], "model_config_id": model["id"]},
        )
        assert resp.status_code == 400
        assert "judge_model_config_id" in resp.json()["detail"]

    async def test_unparseable_judge_verdict_marks_zero(self, client, monkeypatch):
        candidate = FakeLLMClient(responder=lambda p: "some answer")
        judge = FakeLLMClient(responder=lambda p: "I refuse to grade this.")

        def factory(model_config):
            return judge if model_config.name == "judge-model" else candidate

        monkeypatch.setattr(dispatcher, "create_llm_client", factory)

        model = await create_test_model(client, name="candidate-model")
        judge_model = await create_test_model(client, name="judge-model")
        ds = await import_dataset(client, "llm_judge", max_items=1)
        run = (
            await client.post(
                "/api/runs/",
                json={
                    "dataset_id": ds["id"],
                    "model_config_id": model["id"],
                    "judge_model_config_id": judge_model["id"],
                },
            )
        ).json()
        final = await wait_for_run_terminal(client, run["id"])
        assert final["status"] == "completed"
        assert final["aggregate_score"] == 0.0
        tasks = (await client.get(f"/api/runs/{run['id']}/tasks")).json()
        assert "error" in tasks["tasks"][0]["evaluation_details"]
