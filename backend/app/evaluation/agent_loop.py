import json

from app.evaluation.base import BaseEvaluator, EvalResult


class AgentLoopEvaluator(BaseEvaluator):
    """Scores a recorded multi-turn agent trajectory.

    Follows the standard agent-eval dimensions: task completion (did the
    final answer meet the goal), tool use (right tools, right order, right
    arguments), and efficiency (finished within a sensible turn budget).
    The dispatcher injects the recorded trajectory as metadata["_trajectory"].
    """

    def parse_answer(self, raw_response: str, metadata: dict | None = None) -> str:
        return (raw_response or "").strip()

    @staticmethod
    def _subsequence_matches(expected: list[str], actual: list[str]) -> int:
        """How many of `expected` appear in `actual` in relative order."""
        matched = 0
        pos = 0
        for tool in expected:
            for i in range(pos, len(actual)):
                if actual[i] == tool:
                    matched += 1
                    pos = i + 1
                    break
        return matched

    def score(
        self,
        parsed_answer: str,
        reference_answer: str,
        metadata: dict | None = None,
    ) -> EvalResult:
        metadata = metadata or {}

        try:
            ref = json.loads(reference_answer)
        except (json.JSONDecodeError, TypeError):
            return EvalResult(
                is_correct=False,
                score=0.0,
                details={"error": "Invalid reference_answer JSON"},
            )

        trajectory: list[dict] = metadata.get("_trajectory", [])
        max_turns = int(metadata.get("max_turns", 6))
        actions = [step["action"] for step in trajectory if step.get("action")]
        actual_sequence = [a.get("tool", "") for a in actions]
        turns_used = len(trajectory)
        finished = any("final_answer" in step for step in trajectory)

        # --- Task completion (0.4) ---
        expected_final = ref.get("expected_final_answer", "")
        keywords = ref.get("final_answer_keywords", [])
        answer_lower = parsed_answer.lower()
        if expected_final:
            completion_score = 1.0 if expected_final.lower() in answer_lower else 0.0
        elif keywords:
            found = sum(1 for kw in keywords if str(kw).lower() in answer_lower)
            completion_score = found / len(keywords)
        else:
            completion_score = 1.0 if finished and parsed_answer else 0.0

        # --- Tool usage: sequence + arguments (0.4) ---
        expected_sequence = ref.get("expected_tool_sequence", [])
        if expected_sequence:
            matched = self._subsequence_matches(expected_sequence, actual_sequence)
            sequence_score = matched / len(expected_sequence)
        else:
            sequence_score = 1.0

        expected_args = ref.get("expected_tool_args", {})
        if expected_args:
            arg_hits = 0
            arg_total = 0
            for tool_name, expectations in expected_args.items():
                first_call = next(
                    (a for a in actions if a.get("tool") == tool_name), None
                )
                for param, expected_value in expectations.items():
                    arg_total += 1
                    if first_call is not None:
                        actual_value = str(first_call.get("args", {}).get(param, ""))
                        if str(expected_value).lower() in actual_value.lower():
                            arg_hits += 1
            args_score = arg_hits / arg_total if arg_total else 1.0
            tool_score = 0.6 * sequence_score + 0.4 * args_score
        else:
            args_score = None
            tool_score = sequence_score

        # --- Efficiency (0.2) ---
        if not finished:
            efficiency_score = 0.0
        else:
            expected_turns = int(
                ref.get("max_expected_turns", len(expected_sequence) + 1 or 2)
            )
            if turns_used <= expected_turns:
                efficiency_score = 1.0
            elif turns_used >= max_turns:
                efficiency_score = 0.3
            else:
                span = max(1, max_turns - expected_turns)
                efficiency_score = 1.0 - 0.7 * (turns_used - expected_turns) / span

        total = 0.4 * completion_score + 0.4 * tool_score + 0.2 * efficiency_score

        details = {
            "completion_score": round(completion_score, 4),
            "tool_score": round(tool_score, 4),
            "sequence_score": round(sequence_score, 4),
            "efficiency_score": round(efficiency_score, 4),
            "expected_tool_sequence": expected_sequence,
            "actual_tool_sequence": actual_sequence,
            "turns_used": turns_used,
            "finished_with_final_answer": finished,
        }
        if args_score is not None:
            details["args_score"] = round(args_score, 4)

        return EvalResult(
            is_correct=total >= 0.99,
            score=round(total, 4),
            details=details,
        )
