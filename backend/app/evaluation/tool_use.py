import json
import re

from app.evaluation.base import BaseEvaluator, EvalResult


class ToolUseEvaluator(BaseEvaluator):
    """Evaluates whether an agent correctly selects and calls the right tool
    with the correct parameters."""

    def parse_answer(self, raw_response: str, metadata: dict | None = None) -> str:
        """Extract a tool call from the agent response.

        Looks for JSON with "tool_name" and "parameters" fields, or
        function_call patterns like ``function_name(arg=value)``.
        """
        # Strategy 1: find a JSON object with tool_name
        json_objects = re.findall(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", raw_response)
        for candidate in json_objects:
            try:
                parsed = json.loads(candidate)
                if "tool_name" in parsed:
                    return json.dumps(parsed)
            except (json.JSONDecodeError, TypeError):
                continue

        # Strategy 2: function_call style  e.g. function_call: search(query="weather")
        fc_match = re.search(
            r"(?:function_call|tool_call|action)\s*[:=]\s*(\w+)\(([^)]*)\)",
            raw_response,
            re.IGNORECASE,
        )
        if fc_match:
            tool_name = fc_match.group(1)
            params_str = fc_match.group(2)
            parameters: dict[str, str] = {}
            for param_match in re.finditer(
                r"(\w+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|(\S+))", params_str
            ):
                key = param_match.group(1)
                value = (
                    param_match.group(2)
                    or param_match.group(3)
                    or param_match.group(4)
                )
                parameters[key] = value
            return json.dumps({"tool_name": tool_name, "parameters": parameters})

        # Strategy 3: look for tool name mentioned with a JSON block nearby
        tool_match = re.search(r"(?:tool|function)\s*[:=]\s*[\"']?(\w+)[\"']?", raw_response, re.IGNORECASE)
        if tool_match:
            tool_name = tool_match.group(1)
            return json.dumps({"tool_name": tool_name, "parameters": {}})

        return raw_response.strip()

    def score(
        self,
        parsed_answer: str,
        reference_answer: str,
        metadata: dict | None = None,
    ) -> EvalResult:
        metadata = metadata or {}
        partial_credit = metadata.get("partial_credit", True)

        try:
            ref = json.loads(reference_answer)
        except (json.JSONDecodeError, TypeError):
            return EvalResult(
                is_correct=False,
                score=0.0,
                details={"error": "Invalid reference_answer JSON"},
            )

        try:
            answer = json.loads(parsed_answer)
        except (json.JSONDecodeError, TypeError):
            return EvalResult(
                is_correct=False,
                score=0.0,
                details={"error": "Could not parse tool call from response"},
            )

        ref_tool = ref.get("tool_name", "")
        ref_params = ref.get("parameters", {})
        ans_tool = answer.get("tool_name", "")
        ans_params = answer.get("parameters", {})

        # --- Tool name check (0.4) ---
        tool_correct = ans_tool.lower().strip() == ref_tool.lower().strip()
        tool_score = 1.0 if tool_correct else 0.0

        # --- Required parameters present (0.3) ---
        if ref_params:
            present_count = sum(1 for k in ref_params if k in ans_params)
            params_present_score = present_count / len(ref_params)
        else:
            params_present_score = 1.0

        # --- Parameter values correct (0.3) ---
        if ref_params:
            correct_count = 0
            for k, v in ref_params.items():
                if k in ans_params:
                    if str(ans_params[k]).strip().lower() == str(v).strip().lower():
                        correct_count += 1
            params_value_score = correct_count / len(ref_params)
        else:
            params_value_score = 1.0

        total = 0.4 * tool_score + 0.3 * params_present_score + 0.3 * params_value_score

        if not partial_credit:
            total = 1.0 if total == 1.0 else 0.0

        return EvalResult(
            is_correct=total == 1.0,
            score=round(total, 4),
            details={
                "tool_correct": tool_correct,
                "tool_score": tool_score,
                "params_present_score": round(params_present_score, 4),
                "params_value_score": round(params_value_score, 4),
                "expected_tool": ref_tool,
                "actual_tool": ans_tool,
                "expected_params": ref_params,
                "actual_params": ans_params,
            },
        )
