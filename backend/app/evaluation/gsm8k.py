import math
import re

from app.evaluation.base import BaseEvaluator, EvalResult


class GSM8KEvaluator(BaseEvaluator):
    def parse_answer(self, raw_response: str, metadata: dict | None = None) -> str:
        # Look for #### pattern first
        match = re.search(r"####\s*(-?[\d,]+\.?\d*)", raw_response)
        if match:
            return match.group(1).replace(",", "")

        # Fall back to last number in the response
        numbers = re.findall(r"-?[\d,]+\.?\d*", raw_response)
        if numbers:
            return numbers[-1].replace(",", "")

        return ""

    def score(self, parsed_answer: str, reference_answer: str, metadata: dict | None = None) -> EvalResult:
        try:
            parsed_val = float(parsed_answer)
        except (ValueError, TypeError):
            return EvalResult(
                is_correct=False,
                score=0.0,
                details={"error": "Could not parse answer as number", "parsed": parsed_answer},
            )

        try:
            ref_clean = reference_answer.replace(",", "")
            # Handle #### prefix in reference
            if "####" in ref_clean:
                ref_clean = ref_clean.split("####")[-1].strip()
            ref_val = float(ref_clean)
        except (ValueError, TypeError):
            return EvalResult(
                is_correct=False,
                score=0.0,
                details={"error": "Could not parse reference as number", "reference": reference_answer},
            )

        is_correct = math.isclose(parsed_val, ref_val, rel_tol=1e-5, abs_tol=1e-8)
        return EvalResult(
            is_correct=is_correct,
            score=1.0 if is_correct else 0.0,
            details={"parsed_value": parsed_val, "reference_value": ref_val},
        )
