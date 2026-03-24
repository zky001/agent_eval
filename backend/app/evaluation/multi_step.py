import json
import re

from app.evaluation.base import BaseEvaluator, EvalResult


class MultiStepEvaluator(BaseEvaluator):
    """Evaluates whether an agent correctly decomposes a complex task into a
    sequence of steps."""

    def parse_answer(self, raw_response: str, metadata: dict | None = None) -> str:
        """Extract numbered steps or a structured plan from the response.

        Returns a JSON string with a ``"steps"`` list.
        """
        # Try JSON first
        try:
            parsed = json.loads(raw_response)
            if isinstance(parsed, dict) and "steps" in parsed:
                return json.dumps(parsed)
        except (json.JSONDecodeError, TypeError):
            pass

        # Look for numbered steps: "1. ...", "1) ...", "Step 1: ..."
        step_patterns = [
            re.findall(r"(?:^|\n)\s*(?:step\s*)?\d+[\.\):\-]\s*(.+)", raw_response, re.IGNORECASE),
            re.findall(r"(?:^|\n)\s*[-*]\s+(.+)", raw_response),
        ]

        for steps in step_patterns:
            if steps:
                cleaned = [s.strip() for s in steps if s.strip()]
                return json.dumps({"steps": cleaned})

        # Fall back: split by newlines and treat non-empty lines as steps
        lines = [line.strip() for line in raw_response.strip().splitlines() if line.strip()]
        if lines:
            return json.dumps({"steps": lines})

        return json.dumps({"steps": []})

    def _fuzzy_match(self, candidate: str, reference: str) -> bool:
        """Check if reference is a substring of candidate (case-insensitive)."""
        return reference.strip().lower() in candidate.strip().lower()

    def _find_step_index(self, steps: list[str], target: str) -> int:
        """Return the index of the first step that fuzzy-matches target, or -1."""
        for i, step in enumerate(steps):
            if self._fuzzy_match(step, target):
                return i
        return -1

    def score(
        self,
        parsed_answer: str,
        reference_answer: str,
        metadata: dict | None = None,
    ) -> EvalResult:
        metadata = metadata or {}
        strict_order = metadata.get("strict_order", False)

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
                details={"error": "Could not parse steps from response"},
            )

        ref_steps = ref.get("steps", [])
        key_steps = ref.get("key_steps", [])
        ans_steps = answer.get("steps", [])

        # --- Step count match (0.2) ---
        if ref_steps:
            count_ratio = 1.0 - abs(len(ans_steps) - len(ref_steps)) / max(len(ref_steps), 1)
            step_count_score = max(0.0, count_ratio)
        else:
            step_count_score = 1.0 if not ans_steps else 0.0

        # --- Key steps present (0.5) ---
        if key_steps:
            found = sum(
                1
                for ks in key_steps
                if any(self._fuzzy_match(ans, ks) for ans in ans_steps)
            )
            key_steps_score = found / len(key_steps)
        else:
            key_steps_score = 1.0

        # --- Correct ordering (0.3) ---
        if ref_steps and ans_steps:
            if strict_order:
                # All reference steps must appear in the same relative order
                indices = [self._find_step_index(ans_steps, rs) for rs in ref_steps]
                valid_indices = [i for i in indices if i >= 0]
                if len(valid_indices) >= 2:
                    in_order = sum(
                        1
                        for a, b in zip(valid_indices, valid_indices[1:])
                        if a < b
                    )
                    order_score = in_order / (len(valid_indices) - 1)
                elif valid_indices:
                    order_score = 1.0
                else:
                    order_score = 0.0
            else:
                # Relaxed: just check that key steps appear in the right relative order
                targets = key_steps if key_steps else ref_steps
                indices = [self._find_step_index(ans_steps, t) for t in targets]
                valid_indices = [i for i in indices if i >= 0]
                if len(valid_indices) >= 2:
                    in_order = sum(
                        1
                        for a, b in zip(valid_indices, valid_indices[1:])
                        if a < b
                    )
                    order_score = in_order / (len(valid_indices) - 1)
                elif valid_indices:
                    order_score = 1.0
                else:
                    order_score = 0.0
        else:
            order_score = 0.0

        total = 0.2 * step_count_score + 0.5 * key_steps_score + 0.3 * order_score

        return EvalResult(
            is_correct=total >= 0.99,
            score=round(total, 4),
            details={
                "step_count_score": round(step_count_score, 4),
                "key_steps_score": round(key_steps_score, 4),
                "order_score": round(order_score, 4),
                "expected_step_count": len(ref_steps),
                "actual_step_count": len(ans_steps),
                "key_steps_found": [
                    ks
                    for ks in key_steps
                    if any(self._fuzzy_match(ans, ks) for ans in ans_steps)
                ],
                "strict_order": strict_order,
            },
        )
