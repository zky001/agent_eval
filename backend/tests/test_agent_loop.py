"""Tests for the multi-turn agent loop: mock tools, trajectory, scoring."""

import json

from app.evaluation.agent_loop import AgentLoopEvaluator
from app.services.agent_loop import (
    execute_mock_tool,
    parse_action,
    run_agent_loop,
)
from tests.conftest import FakeLLMClient

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get weather",
        "parameters": {"city": "city"},
        "responses": [
            {"when_args_contain": {"city": "tokyo"}, "response": "Sunny, no rain"}
        ],
        "response": "unknown city",
    },
    {
        "name": "send_message",
        "description": "Send message",
        "parameters": {"user": "u", "text": "t"},
        "response": "delivered",
    },
    {
        "name": "service_status",
        "description": "Status",
        "parameters": {"service": "s"},
        "responses": [
            {
                "when_args_contain": {"service": "auth"},
                "when_called_after": "restart_service",
                "response": "healthy",
            },
            {"when_args_contain": {"service": "auth"}, "response": "DEGRADED"},
        ],
        "response": "unknown",
    },
    {
        "name": "restart_service",
        "description": "Restart",
        "parameters": {"service": "s"},
        "response": "restarted",
    },
]


class TestParseAction:
    def test_json_args(self):
        assert parse_action('Action: get_weather({"city": "Tokyo"})') == (
            "get_weather",
            {"city": "Tokyo"},
        )

    def test_with_reasoning_text_around(self):
        text = 'I should check the weather.\nAction: get_weather({"city": "Tokyo"})'
        assert parse_action(text) == ("get_weather", {"city": "Tokyo"})

    def test_empty_args(self):
        assert parse_action("Action: list_tools()") == ("list_tools", {})

    def test_malformed_args_kept_raw(self):
        tool, args = parse_action("Action: search(weather in Tokyo)")
        assert tool == "search"
        assert args == {"_raw": "weather in Tokyo"}

    def test_no_action(self):
        assert parse_action("I am not sure what to do.") is None


class TestMockTools:
    def test_rule_match(self):
        obs = execute_mock_tool(TOOLS, "get_weather", {"city": "Tokyo"})
        assert obs == "Sunny, no rain"

    def test_fallback_response(self):
        assert execute_mock_tool(TOOLS, "get_weather", {"city": "Mars"}) == "unknown city"

    def test_unknown_tool(self):
        obs = execute_mock_tool(TOOLS, "nope", {})
        assert "unknown tool" in obs
        assert "get_weather" in obs

    def test_stateful_when_called_after(self):
        # Before restart: degraded; after restart: healthy
        assert execute_mock_tool(TOOLS, "service_status", {"service": "auth"}, set()) == "DEGRADED"
        assert (
            execute_mock_tool(
                TOOLS, "service_status", {"service": "auth"}, {"restart_service"}
            )
            == "healthy"
        )


class TestRunAgentLoop:
    async def test_full_loop_records_trajectory(self):
        script = [
            'Action: get_weather({"city": "Tokyo"})',
            'Action: send_message({"user": "Alice", "text": "clear skies today"})',
            "Final Answer: I told Alice clear skies today.",
        ]
        client = FakeLLMClient(chat_responder=lambda messages: script[
            sum(1 for m in messages if m["role"] == "assistant")
        ])

        outcome = await run_agent_loop(
            client,
            "Check Tokyo weather and notify Alice",
            {"tools": TOOLS, "max_turns": 5},
            {},
        )
        assert outcome.final_answer == "I told Alice clear skies today."
        assert len(outcome.trajectory) == 3
        assert outcome.trajectory[0]["action"]["tool"] == "get_weather"
        assert outcome.trajectory[0]["observation"] == "Sunny, no rain"
        assert outcome.trajectory[1]["action"]["args"]["user"] == "Alice"
        assert outcome.input_tokens == 30 and outcome.output_tokens == 15

        # The model saw the observation as a user message
        second_call_messages = client.chat_calls[1][0]
        assert second_call_messages[-1]["content"] == "Observation: Sunny, no rain"
        # Tools are described in the system prompt
        assert "get_weather" in client.chat_calls[0][1]["system"]

    async def test_hits_max_turns_without_final(self):
        client = FakeLLMClient(
            chat_responder=lambda m: 'Action: get_weather({"city": "Tokyo"})'
        )
        outcome = await run_agent_loop(
            client, "task", {"tools": TOOLS, "max_turns": 3}, {}
        )
        assert outcome.final_answer is None
        assert len(outcome.trajectory) == 3

    async def test_nudges_on_unparseable_turn(self):
        script = ["I will think about it.", "Final Answer: done"]
        client = FakeLLMClient(chat_responder=lambda messages: script[
            sum(1 for m in messages if m["role"] == "assistant")
        ])
        outcome = await run_agent_loop(client, "task", {"tools": TOOLS}, {})
        assert outcome.final_answer == "done"
        assert outcome.trajectory[0].get("note") == "no_action_or_final_answer"


class TestAgentLoopEvaluator:
    def setup_method(self):
        self.ev = AgentLoopEvaluator()
        self.ref = json.dumps(
            {
                "final_answer_keywords": ["clear skies", "Alice"],
                "expected_tool_sequence": ["get_weather", "send_message"],
                "expected_tool_args": {"get_weather": {"city": "Tokyo"}},
            }
        )

    def _meta(self, trajectory, max_turns=5):
        return {"_trajectory": trajectory, "max_turns": max_turns}

    def test_perfect_trajectory(self):
        trajectory = [
            {"turn": 1, "action": {"tool": "get_weather", "args": {"city": "Tokyo"}}, "observation": "Sunny"},
            {"turn": 2, "action": {"tool": "send_message", "args": {"user": "Alice", "text": "clear skies"}}, "observation": "delivered"},
            {"turn": 3, "final_answer": "Told Alice clear skies today"},
        ]
        res = self.ev.score(
            "Told Alice clear skies today", self.ref, self._meta(trajectory)
        )
        assert res.score == 1.0 and res.is_correct

    def test_wrong_tool_order_penalized(self):
        trajectory = [
            {"turn": 1, "action": {"tool": "send_message", "args": {}}, "observation": "x"},
            {"turn": 2, "action": {"tool": "get_weather", "args": {"city": "Tokyo"}}, "observation": "y"},
            {"turn": 3, "final_answer": "clear skies, told Alice"},
        ]
        res = self.ev.score("clear skies, told Alice", self.ref, self._meta(trajectory))
        # Only get_weather matches as an in-order subsequence element
        assert res.details["sequence_score"] == 0.5
        assert res.score < 1.0

    def test_no_final_answer_zero_efficiency(self):
        trajectory = [
            {"turn": 1, "action": {"tool": "get_weather", "args": {"city": "Tokyo"}}, "observation": "Sunny"},
        ]
        res = self.ev.score("", self.ref, self._meta(trajectory))
        assert res.details["efficiency_score"] == 0.0
        assert res.details["completion_score"] == 0.0

    def test_excess_turns_decay(self):
        trajectory = [
            {"turn": 1, "action": {"tool": "get_weather", "args": {"city": "Tokyo"}}, "observation": "s"},
            {"turn": 2, "note": "no_action_or_final_answer"},
            {"turn": 3, "action": {"tool": "send_message", "args": {}}, "observation": "d"},
            {"turn": 4, "final_answer": "clear skies Alice"},
        ]
        res = self.ev.score("clear skies Alice", self.ref, self._meta(trajectory))
        assert 0 < res.details["efficiency_score"] < 1.0
