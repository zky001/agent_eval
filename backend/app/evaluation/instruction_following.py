import json
import re

from app.evaluation.base import BaseEvaluator, EvalResult


class InstructionFollowingEvaluator(BaseEvaluator):
    """Evaluates whether an agent follows complex, multi-constraint instructions."""

    def parse_answer(self, raw_response: str, metadata: dict | None = None) -> str:
        """Return the cleaned response text."""
        return raw_response.strip()

    def _check_constraint(self, response: str, constraint: dict) -> bool:
        """Check a single constraint against the response.

        Supported constraint types:
        - format: check response format (e.g. "json", "xml", "csv")
        - contains: check if response contains a value
        - excludes: check if response does NOT contain a value
        - length_max: check response length <= value
        - length_min: check response length >= value
        - starts_with: check if response starts with a value
        - ends_with: check if response ends with a value
        - regex: check if response matches a regex pattern
        """
        ctype = constraint.get("type", "")
        check_val = constraint.get("check", constraint.get("value", ""))

        if ctype == "format":
            fmt = str(check_val).lower()
            if fmt == "json":
                try:
                    json.loads(response)
                    return True
                except (json.JSONDecodeError, TypeError):
                    return False
            elif fmt == "xml":
                return bool(re.search(r"<\w+.*?>.*?</\w+>", response, re.DOTALL))
            elif fmt == "csv":
                lines = response.strip().splitlines()
                return len(lines) >= 1 and "," in lines[0]
            elif fmt == "markdown":
                return bool(re.search(r"[#*\-|`]", response))
            else:
                return False

        elif ctype == "contains":
            return str(check_val).lower() in response.lower()

        elif ctype == "excludes":
            return str(check_val).lower() not in response.lower()

        elif ctype == "length_max":
            try:
                return len(response) <= int(check_val)
            except (ValueError, TypeError):
                return False

        elif ctype == "length_min":
            try:
                return len(response) >= int(check_val)
            except (ValueError, TypeError):
                return False

        elif ctype == "starts_with":
            return response.lower().startswith(str(check_val).lower())

        elif ctype == "ends_with":
            return response.lower().endswith(str(check_val).lower())

        elif ctype == "regex":
            try:
                return bool(re.search(str(check_val), response))
            except re.error:
                return False

        else:
            # Unknown constraint type - skip gracefully
            return False

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

        constraints = ref.get("constraints", [])
        if not constraints:
            return EvalResult(
                is_correct=True,
                score=1.0,
                details={"message": "No constraints to check"},
            )

        results: list[dict] = []
        passed = 0

        for constraint in constraints:
            met = self._check_constraint(parsed_answer, constraint)
            results.append({
                "constraint": constraint,
                "met": met,
            })
            if met:
                passed += 1

        total = passed / len(constraints)

        return EvalResult(
            is_correct=total == 1.0,
            score=round(total, 4),
            details={
                "constraints_total": len(constraints),
                "constraints_met": passed,
                "constraint_results": results,
            },
        )
