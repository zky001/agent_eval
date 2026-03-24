from app.evaluation.base import BaseEvaluator, EvalResult


class CustomEvaluator(BaseEvaluator):
    def parse_answer(self, raw_response: str, metadata: dict | None = None) -> str:
        return raw_response.strip()

    def score(self, parsed_answer: str, reference_answer: str, metadata: dict | None = None) -> EvalResult:
        metadata = metadata or {}
        match_type = metadata.get("match_type", "exact")

        if match_type == "contains":
            is_correct = reference_answer.strip().lower() in parsed_answer.lower()
            return EvalResult(
                is_correct=is_correct,
                score=1.0 if is_correct else 0.0,
                details={
                    "match_type": "contains",
                    "parsed": parsed_answer,
                    "reference": reference_answer,
                },
            )
        else:
            # Exact match
            is_correct = parsed_answer.strip().lower() == reference_answer.strip().lower()
            return EvalResult(
                is_correct=is_correct,
                score=1.0 if is_correct else 0.0,
                details={
                    "match_type": "exact",
                    "parsed": parsed_answer,
                    "reference": reference_answer,
                },
            )
