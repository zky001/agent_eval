import json

from app.evaluation.api_interaction import APIInteractionEvaluator
from app.evaluation.custom import CustomEvaluator
from app.evaluation.error_recovery import ErrorRecoveryEvaluator
from app.evaluation.gsm8k import GSM8KEvaluator
from app.evaluation.humaneval import HumanEvalEvaluator
from app.evaluation.instruction_following import InstructionFollowingEvaluator
from app.evaluation.mmlu import MMLUEvaluator
from app.evaluation.multi_step import MultiStepEvaluator
from app.evaluation.react import ReActEvaluator
from app.evaluation.registry import EvaluatorRegistry
from app.evaluation.tool_use import ToolUseEvaluator


class TestRegistry:
    def test_known_types(self):
        assert isinstance(EvaluatorRegistry.get("gsm8k"), GSM8KEvaluator)
        assert isinstance(EvaluatorRegistry.get("MMLU"), MMLUEvaluator)

    def test_unknown_type_falls_back_to_custom(self):
        assert isinstance(EvaluatorRegistry.get("nope"), CustomEvaluator)


class TestGSM8K:
    def setup_method(self):
        self.ev = GSM8KEvaluator()

    def test_hash_pattern(self):
        assert self.ev.parse_answer("blah blah\n#### 1,234") == "1234"

    def test_boxed_pattern(self):
        assert self.ev.parse_answer(r"So the total is \boxed{72}.") == "72"

    def test_answer_is_pattern(self):
        assert self.ev.parse_answer("The answer is $18 per day") == "18"

    def test_last_number_fallback(self):
        assert self.ev.parse_answer("She makes 16 eggs and sells 9") == "9"

    def test_score_match_with_reference_prefix(self):
        res = self.ev.score("18", "#### 18")
        assert res.is_correct and res.score == 1.0

    def test_score_mismatch(self):
        res = self.ev.score("17", "#### 18")
        assert not res.is_correct and res.score == 0.0

    def test_score_unparseable(self):
        res = self.ev.score("", "#### 18")
        assert not res.is_correct


class TestMMLU:
    def setup_method(self):
        self.ev = MMLUEvaluator()

    def test_answer_prefix(self):
        assert self.ev.parse_answer("Answer: C") == "C"

    def test_the_answer_is(self):
        assert self.ev.parse_answer("Reasoning... The answer is (b)") == "B"

    def test_bare_letter(self):
        assert self.ev.parse_answer("D") == "D"

    def test_score(self):
        assert self.ev.score("c", "C").is_correct
        assert not self.ev.score("A", "C").is_correct


class TestHumanEval:
    def setup_method(self):
        self.ev = HumanEvalEvaluator()

    def test_parse_code_block(self):
        raw = "Here you go:\n```python\ndef add(a, b):\n    return a + b\n```"
        assert self.ev.parse_answer(raw) == "def add(a, b):\n    return a + b"

    def test_score_passing_tests(self):
        code = "def add(a, b):\n    return a + b"
        meta = {"test_cases": "assert add(1, 2) == 3"}
        res = self.ev.score(code, "", meta)
        assert res.is_correct and res.score == 1.0

    def test_score_failing_tests(self):
        code = "def add(a, b):\n    return a - b"
        meta = {"test_cases": "assert add(1, 2) == 3"}
        res = self.ev.score(code, "", meta)
        assert not res.is_correct

    def test_score_syntax_only_without_tests(self):
        assert self.ev.score("x = 1", "", {}).is_correct
        assert not self.ev.score("def broken(:", "", {}).is_correct

    def test_infinite_loop_times_out(self):
        res = self.ev.score("while True: pass", "", {"test_cases": "assert True"})
        assert not res.is_correct
        assert "timed out" in res.details["error"]


class TestToolUse:
    def setup_method(self):
        self.ev = ToolUseEvaluator()
        self.ref = json.dumps(
            {"tool_name": "weather", "parameters": {"city": "Tokyo"}}
        )

    def test_parse_json_response(self):
        raw = 'I will call {"tool_name": "weather", "parameters": {"city": "Tokyo"}}'
        parsed = json.loads(self.ev.parse_answer(raw))
        assert parsed["tool_name"] == "weather"

    def test_parse_function_call_style(self):
        raw = 'action: weather(city="Tokyo")'
        parsed = json.loads(self.ev.parse_answer(raw))
        assert parsed == {"tool_name": "weather", "parameters": {"city": "Tokyo"}}

    def test_perfect_score(self):
        ans = json.dumps({"tool_name": "weather", "parameters": {"city": "tokyo"}})
        res = self.ev.score(ans, self.ref)
        assert res.is_correct and res.score == 1.0

    def test_wrong_tool_partial_credit(self):
        ans = json.dumps({"tool_name": "search", "parameters": {"city": "Tokyo"}})
        res = self.ev.score(ans, self.ref)
        assert not res.is_correct
        assert 0 < res.score < 1

    def test_unparseable_answer(self):
        res = self.ev.score("just words", self.ref)
        assert res.score == 0.0


class TestMultiStep:
    def setup_method(self):
        self.ev = MultiStepEvaluator()

    def test_parse_numbered_steps(self):
        raw = "1. Run tests\n2. Build artifacts\n3. Deploy"
        parsed = json.loads(self.ev.parse_answer(raw))
        assert parsed["steps"] == ["Run tests", "Build artifacts", "Deploy"]

    def test_score_all_key_steps_in_order(self):
        ref = json.dumps(
            {"steps": ["run tests", "build", "deploy"], "key_steps": ["test", "build", "deploy"]}
        )
        ans = json.dumps({"steps": ["Run the tests", "Build the app", "Deploy to prod"]})
        res = self.ev.score(ans, ref)
        assert res.score == 1.0

    def test_score_missing_key_steps(self):
        ref = json.dumps({"steps": ["a", "b"], "key_steps": ["backup", "deploy"]})
        ans = json.dumps({"steps": ["deploy it"]})
        res = self.ev.score(ans, ref)
        assert res.details["key_steps_found"] == ["deploy"]
        assert res.score < 1.0


class TestReAct:
    def setup_method(self):
        self.ev = ReActEvaluator()

    def test_parse_react_blocks(self):
        raw = (
            "Thought: I need the weather\n"
            "Action: get_weather(London)\n"
            "Observation: rainy\n"
            "Thought: notify Alice\n"
            "Action: send_message(Alice, rain)\n"
        )
        parsed = json.loads(self.ev.parse_answer(raw))
        assert len(parsed["thoughts"]) == 2
        assert len(parsed["actions"]) == 2
        assert parsed["final_action"] == "send_message(Alice, rain)"

    def test_score_full_match(self):
        ref = json.dumps(
            {"expected_action": "send_message(Alice", "key_concepts": ["weather", "Alice"]}
        )
        parsed = self.ev.parse_answer(
            "Thought: check weather in London\nAction: get_weather(London)\n"
            "Observation: rain\nThought: tell Alice\nAction: send_message(Alice, it will rain)"
        )
        res = self.ev.score(parsed, ref, {"min_reasoning_steps": 2})
        assert res.score >= 0.9


class TestInstructionFollowing:
    def setup_method(self):
        self.ev = InstructionFollowingEvaluator()

    def test_constraints_pass(self):
        ref = json.dumps(
            {
                "constraints": [
                    {"type": "format", "check": "json"},
                    {"type": "contains", "check": "benefits"},
                    {"type": "length_max", "check": 500},
                ]
            }
        )
        ans = '{"benefits": ["a", "b", "c"]}'
        res = self.ev.score(ans, ref)
        assert res.is_correct and res.score == 1.0

    def test_constraints_partial(self):
        ref = json.dumps(
            {
                "constraints": [
                    {"type": "starts_with", "check": "The waves"},
                    {"type": "excludes", "check": "blue"},
                ]
            }
        )
        res = self.ev.score("The waves are blue.", ref)
        assert not res.is_correct
        assert res.score == 0.5


class TestAPIInteraction:
    def setup_method(self):
        self.ev = APIInteractionEvaluator()
        self.ref = json.dumps(
            {
                "method": "POST",
                "endpoint": "https://api.example.com/users",
                "required_headers": {"Content-Type": "application/json"},
                "body": {"name": "John Doe", "email": "john@example.com"},
            }
        )

    def test_full_match_from_json_response(self):
        raw = json.dumps(
            {
                "method": "POST",
                "endpoint": "https://api.example.com/users",
                "headers": {"Content-Type": "application/json"},
                "body": {"name": "John Doe", "email": "john@example.com"},
            }
        )
        parsed = self.ev.parse_answer(raw)
        res = self.ev.score(parsed, self.ref)
        assert res.is_correct and res.score == 1.0

    def test_http_style_parse(self):
        raw = (
            "POST https://api.example.com/users\n"
            "Content-Type: application/json\n\n"
            '```json\n{"name": "John Doe", "email": "john@example.com"}\n```'
        )
        parsed = json.loads(self.ev.parse_answer(raw))
        assert parsed["method"] == "POST"
        assert parsed["endpoint"] == "https://api.example.com/users"
        assert parsed["headers"] == {"Content-Type": "application/json"}
        assert parsed["body"] == {"name": "John Doe", "email": "john@example.com"}

    def test_wrong_method_partial(self):
        raw = json.dumps(
            {
                "method": "GET",
                "endpoint": "https://api.example.com/users",
                "headers": {"Content-Type": "application/json"},
                "body": {"name": "John Doe", "email": "john@example.com"},
            }
        )
        res = self.ev.score(self.ev.parse_answer(raw), self.ref)
        assert not res.is_correct
        assert res.details["method_score"] == 0.0


class TestErrorRecovery:
    def setup_method(self):
        self.ev = ErrorRecoveryEvaluator()

    def test_good_diagnosis(self):
        ref = json.dumps(
            {
                "error_detected": True,
                "diagnosis_keywords": ["KeyError", "users"],
                "action_keywords": ["results"],
                "explanation_keywords": ["key"],
            }
        )
        raw = (
            "The code crashes because of a KeyError: the response has no 'users' key.\n"
            "Fix: replace data['users'] with data['results'] to read the results key.\n"
            "Explanation: the API nests the list under the key 'results', not 'users'."
        )
        parsed = self.ev.parse_answer(raw)
        res = self.ev.score(parsed, ref)
        assert res.score > 0.8


class TestCustom:
    def setup_method(self):
        self.ev = CustomEvaluator()

    def test_exact_match(self):
        assert self.ev.score("Hello", "hello").is_correct

    def test_contains_match(self):
        res = self.ev.score("The answer is Paris, obviously", "paris", {"match_type": "contains"})
        assert res.is_correct
