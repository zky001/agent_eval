import re

from app.evaluation.base import BaseEvaluator, EvalResult


class MMLUEvaluator(BaseEvaluator):
    def parse_answer(self, raw_response: str, metadata: dict | None = None) -> str:
        # Try "Answer: X" pattern
        match = re.search(r"[Aa]nswer\s*[:is]*\s*\(?([A-Da-d])\)?", raw_response)
        if match:
            return match.group(1).upper()

        # Try "The answer is X" pattern
        match = re.search(r"[Tt]he answer is\s*\(?([A-Da-d])\)?", raw_response)
        if match:
            return match.group(1).upper()

        # Try standalone letter at the end
        match = re.search(r"\b([A-Da-d])\s*[.\):]?\s*$", raw_response.strip())
        if match:
            return match.group(1).upper()

        # Try first standalone letter
        match = re.search(r"^[.\s]*\(?([A-Da-d])\)?[\s.\):]", raw_response.strip())
        if match:
            return match.group(1).upper()

        # Last resort: find any standalone A-D
        match = re.search(r"\b([A-Da-d])\b", raw_response)
        if match:
            return match.group(1).upper()

        return ""

    def score(self, parsed_answer: str, reference_answer: str, metadata: dict | None = None) -> EvalResult:
        parsed_upper = parsed_answer.strip().upper()
        reference_upper = reference_answer.strip().upper()
        is_correct = parsed_upper == reference_upper
        return EvalResult(
            is_correct=is_correct,
            score=1.0 if is_correct else 0.0,
            details={"parsed": parsed_upper, "reference": reference_upper},
        )
