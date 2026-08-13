import json

from tests.conftest import wait_until


async def create_test_model(client, name="test-model", provider="openai"):
    resp = await client.post(
        "/api/models/",
        json={
            "name": name,
            "provider": provider,
            "model_id": "gpt-test",
            "api_key": "sk-secret-key-12345",
            "default_params": {"temperature": 0},
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def import_dataset(client, source="gsm8k", max_items=None):
    body = {"source": source}
    if max_items:
        body["max_items"] = max_items
    resp = await client.post("/api/datasets/import", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def wait_for_run_terminal(client, run_id, timeout=15.0):
    async def check():
        resp = await client.get(f"/api/runs/{run_id}")
        assert resp.status_code == 200
        run = resp.json()
        if run["status"] not in ("pending", "running"):
            return run
        return None

    return await wait_until(check, timeout=timeout)


async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


class TestModels:
    async def test_create_masks_api_key(self, client):
        model = await create_test_model(client)
        assert model["api_key"] == "sk-...2345"

    async def test_duplicate_name_conflict(self, client):
        await create_test_model(client)
        resp = await client.post(
            "/api/models/",
            json={"name": "test-model", "provider": "openai", "model_id": "x"},
        )
        assert resp.status_code == 409

    async def test_update_with_masked_key_keeps_real_key(self, client, fake_llm):
        model = await create_test_model(client)
        # Simulate an edit form echoing the masked key back
        resp = await client.put(
            f"/api/models/{model['id']}",
            json={"name": "renamed", "api_key": "sk-...2345"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "renamed"

        # The stored key must still be the original, not the mask
        from app.database import async_session
        from app.models.model_config import ModelConfig

        async with async_session() as db:
            stored = await db.get(ModelConfig, model["id"])
            assert stored.api_key == "sk-secret-key-12345"

    async def test_update_with_new_key_replaces(self, client):
        model = await create_test_model(client)
        resp = await client.put(
            f"/api/models/{model['id']}",
            json={"api_key": "sk-brand-new-key-9999"},
        )
        assert resp.status_code == 200
        assert resp.json()["api_key"] == "sk-...9999"


class TestDatasets:
    async def test_import_and_list(self, client):
        ds = await import_dataset(client, "gsm8k")
        assert ds["total_items"] == 10

        resp = await client.get("/api/datasets/")
        assert len(resp.json()) == 1

        items = (await client.get(f"/api/datasets/{ds['id']}/items")).json()
        assert len(items) == 10
        assert items[0]["item_index"] == 0

    async def test_import_duplicate_conflict(self, client):
        await import_dataset(client, "mmlu")
        resp = await client.post("/api/datasets/import", json={"source": "mmlu"})
        assert resp.status_code == 409

    async def test_import_unknown_source(self, client):
        resp = await client.post("/api/datasets/import", json={"source": "nope"})
        assert resp.status_code == 400

    async def test_max_items(self, client):
        ds = await import_dataset(client, "gsm8k", max_items=3)
        assert ds["total_items"] == 3

    async def test_upload_custom(self, client):
        resp = await client.post(
            "/api/datasets/upload",
            params={"name": "my-set", "dataset_type": "custom"},
            json=[
                {"prompt": "Say hi", "reference_answer": "hi"},
                {"prompt": "Say bye", "reference_answer": "bye"},
            ],
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["total_items"] == 2


class TestRunLifecycle:
    async def test_run_completes_and_scores(self, client, fake_llm):
        """Full happy path: model responses scored by the gsm8k evaluator."""
        answers = {
            "Janet": "#### 18",  # correct
            "robe": "#### 3",  # correct
            "Josh": "#### 999",  # wrong
        }

        def responder(prompt):
            for key, ans in answers.items():
                if key in prompt:
                    return ans
            return "#### 0"

        fake_llm.responder = responder

        model = await create_test_model(client)
        ds = await import_dataset(client, "gsm8k", max_items=3)

        resp = await client.post(
            "/api/runs/",
            json={"dataset_id": ds["id"], "model_config_id": model["id"]},
        )
        assert resp.status_code == 200, resp.text
        run = resp.json()
        assert run["dataset_name"] == "gsm8k"
        assert run["model_name"] == "test-model"

        final = await wait_for_run_terminal(client, run["id"])
        assert final["status"] == "completed"
        assert final["total_tasks"] == 3
        assert final["completed_tasks"] == 3
        assert final["failed_tasks"] == 0
        assert abs(final["aggregate_score"] - 2 / 3) < 1e-6
        assert final["correct_tasks"] == 2
        assert final["total_tokens"] == 45  # 15 per task
        assert fake_llm.closed

        # Task detail payload includes evaluation details
        tasks = (await client.get(f"/api/runs/{run['id']}/tasks")).json()
        assert tasks["total"] == 3
        first = tasks["tasks"][0]
        assert first["raw_response"] == "#### 18"
        assert first["parsed_answer"] == "18"
        assert first["is_correct"] is True
        assert first["evaluation_details"]["reference_value"] == 18.0

        # Filtering by correctness
        incorrect = (
            await client.get(
                f"/api/runs/{run['id']}/tasks", params={"is_correct": False}
            )
        ).json()
        assert incorrect["total"] == 1

        # Leaderboard reflects the run with equal-weight averaging
        board = (await client.get("/api/leaderboard/")).json()
        assert len(board) == 1
        entry = board[0]
        assert entry["model_name"] == "test-model"
        assert abs(entry["score"] - 66.67) < 0.01
        assert entry["completed_runs"] == 1
        assert entry["avg_latency"] == 7

    async def test_default_params_merged_with_override(self, client, fake_llm):
        model = await create_test_model(client)
        ds = await import_dataset(client, "gsm8k", max_items=1)
        resp = await client.post(
            "/api/runs/",
            json={
                "dataset_id": ds["id"],
                "model_config_id": model["id"],
                "params_override": {"max_tokens": 64},
            },
        )
        run = resp.json()
        await wait_for_run_terminal(client, run["id"])
        assert fake_llm.calls, "fake LLM was never invoked"
        _, params = fake_llm.calls[0]
        assert params == {"temperature": 0, "max_tokens": 64}

    async def test_failed_llm_calls_mark_run_failed(self, client, fake_llm):
        fake_llm.responder = lambda prompt: RuntimeError("api exploded")
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
        assert "failed" in final["error_message"].lower()

    async def test_batch_creates_cartesian_product(self, client, fake_llm):
        fake_llm.responder = lambda prompt: "#### 1"
        model_a = await create_test_model(client, name="model-a")
        model_b = await create_test_model(client, name="model-b")
        ds = await import_dataset(client, "gsm8k", max_items=1)

        resp = await client.post(
            "/api/runs/batch",
            json={
                "dataset_ids": [ds["id"]],
                "model_config_ids": [model_a["id"], model_b["id"]],
            },
        )
        assert resp.status_code == 200
        runs = resp.json()
        assert len(runs) == 2
        for run in runs:
            final = await wait_for_run_terminal(client, run["id"])
            assert final["status"] == "completed"

    async def test_missing_dataset_404(self, client, fake_llm):
        model = await create_test_model(client)
        resp = await client.post(
            "/api/runs/",
            json={"dataset_id": 9999, "model_config_id": model["id"]},
        )
        assert resp.status_code == 404

    async def test_cancel_preserves_cancelled_status(self, client, fake_llm):
        """Regression test: finalization used to overwrite 'cancelled' with
        'completed'."""
        fake_llm.responder = lambda prompt: "#### 18"
        fake_llm.delay = 0.4

        model = await create_test_model(client)
        ds = await import_dataset(client, "gsm8k")  # 10 items
        run = (
            await client.post(
                "/api/runs/",
                json={"dataset_id": ds["id"], "model_config_id": model["id"]},
            )
        ).json()

        resp = await client.post(f"/api/runs/{run['id']}/cancel")
        assert resp.status_code == 200

        # Wait for the executor to drain, then verify status wasn't clobbered
        async def executor_done():
            tasks = (await client.get(f"/api/runs/{run['id']}/tasks")).json()
            active = [
                t
                for t in tasks["tasks"]
                if t["status"] in ("pending", "running")
            ]
            return not active or None

        await wait_until(executor_done, timeout=20)
        final = (await client.get(f"/api/runs/{run['id']}")).json()
        assert final["status"] == "cancelled"

        statuses = {
            t["status"]
            for t in (await client.get(f"/api/runs/{run['id']}/tasks")).json()["tasks"]
        }
        assert statuses <= {"completed", "cancelled", "failed"}

    async def test_delete_run_and_referential_guards(self, client, fake_llm):
        fake_llm.responder = lambda prompt: "#### 18"
        model = await create_test_model(client)
        ds = await import_dataset(client, "gsm8k", max_items=2)
        run = (
            await client.post(
                "/api/runs/",
                json={"dataset_id": ds["id"], "model_config_id": model["id"]},
            )
        ).json()
        await wait_for_run_terminal(client, run["id"])

        # Dataset and model deletion are blocked while runs reference them
        assert (await client.delete(f"/api/datasets/{ds['id']}")).status_code == 409
        assert (await client.delete(f"/api/models/{model['id']}")).status_code == 409

        # Delete the run, then the dataset and model become deletable
        assert (await client.delete(f"/api/runs/{run['id']}")).status_code == 200
        assert (await client.get(f"/api/runs/{run['id']}")).status_code == 404
        assert (await client.delete(f"/api/datasets/{ds['id']}")).status_code == 200
        assert (await client.delete(f"/api/models/{model['id']}")).status_code == 200

    async def test_list_runs_includes_names_and_pagination(self, client, fake_llm):
        fake_llm.responder = lambda prompt: "#### 1"
        model = await create_test_model(client)
        ds = await import_dataset(client, "gsm8k", max_items=1)
        for _ in range(3):
            run = (
                await client.post(
                    "/api/runs/",
                    json={"dataset_id": ds["id"], "model_config_id": model["id"]},
                )
            ).json()
            await wait_for_run_terminal(client, run["id"])

        listed = (await client.get("/api/runs/")).json()
        assert len(listed) == 3
        assert listed[0]["dataset_name"] == "gsm8k"
        assert listed[0]["model_name"] == "test-model"

        page = (await client.get("/api/runs/", params={"skip": 1, "limit": 1})).json()
        assert len(page) == 1


class TestLeaderboardWeighting:
    async def test_runs_weighted_equally_regardless_of_task_count(
        self, client, fake_llm
    ):
        """Regression test for the flat-JOIN fanout bug: a run with many
        tasks must not outweigh a run with few tasks."""
        model = await create_test_model(client)

        # Run 1: 1-item custom dataset, all correct (score 1.0)
        await client.post(
            "/api/datasets/upload",
            params={"name": "small", "dataset_type": "custom"},
            json=[{"prompt": "P1", "reference_answer": "yes"}],
        )
        # Run 2: 4-item custom dataset, all wrong (score 0.0)
        await client.post(
            "/api/datasets/upload",
            params={"name": "big", "dataset_type": "custom"},
            json=[
                {"prompt": f"Q{i}", "reference_answer": "yes"} for i in range(4)
            ],
        )
        datasets = {d["name"]: d for d in (await client.get("/api/datasets/")).json()}

        fake_llm.responder = lambda prompt: "yes" if prompt.startswith("P") else "no"

        for name in ("small", "big"):
            run = (
                await client.post(
                    "/api/runs/",
                    json={
                        "dataset_id": datasets[name]["id"],
                        "model_config_id": model["id"],
                    },
                )
            ).json()
            final = await wait_for_run_terminal(client, run["id"])
            assert final["status"] == "completed"

        # Per-dataset rows on the leaderboard
        board = (await client.get("/api/leaderboard/")).json()
        by_dataset = {e["dataset_name"]: e for e in board}
        assert by_dataset["small"]["score"] == 100.0
        assert by_dataset["big"]["score"] == 0.0
