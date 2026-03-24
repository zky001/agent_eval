import json
import re

from app.evaluation.base import BaseEvaluator, EvalResult


class ErrorRecoveryEvaluator(BaseEvaluator):
    """Evaluates whether an agent can detect errors, diagnose root causes,
    and apply appropriate recovery strategies."""

    def parse_answer(self, raw_response: str, metadata: dict | None = None) -> str:
        """Extract error detection, diagnosis, and recovery action from the response.

        Returns a JSON string with ``"error_detected"``, ``"diagnosis"``,
        ``"recovery_action"``, and ``"explanation"`` fields.
        """
        # Try JSON first
        try:
            parsed = json.loads(raw_response)
            if isinstance(parsed, dict) and ("error_detected" in parsed or "recovery_action" in parsed):
                return json.dumps(parsed)
        except (json.JSONDecodeError, TypeError):
            pass

        result: dict = {
            "error_detected": False,
            "diagnosis": "",
            "recovery_action": "",
            "explanation": "",
        }

        # Detect if the agent identified an error
        error_keywords = [
            r"error", r"bug", r"issue", r"problem", r"fail", r"incorrect",
            r"wrong", r"invalid", r"exception", r"crash", r"broken",
        ]
        response_lower = raw_response.lower()
        result["error_detected"] = any(
            re.search(kw, response_lower) for kw in error_keywords
        )

        # Extract diagnosis: look for "cause", "because", "due to", "root cause"
        diag_match = re.search(
            r"(?:root\s*cause|cause|because|due\s*to|reason|diagnosis)\s*[:=]?\s*(.+?)(?:\n|$)",
            raw_response,
            re.IGNORECASE,
        )
        if diag_match:
            result["diagnosis"] = diag_match.group(1).strip()

        # Extract recovery action: look for "fix", "solution", "recovery", "action"
        recovery_match = re.search(
            r"(?:fix|solution|recovery|corrected?|action|resolve|remedy)\s*[:=]?\s*(.+?)(?:\n\n|\n(?=[A-Z])|\Z)",
            raw_response,
            re.IGNORECASE | re.DOTALL,
        )
        if recovery_match:
            result["recovery_action"] = recovery_match.group(1).strip()[:500]

        # Extract explanation
        explain_match = re.search(
            r"(?:explanation|reasoning|rationale)\s*[:=]?\s*(.+?)(?:\n\n|\Z)",
            raw_response,
            re.IGNORECASE | re.DOTALL,
        )
        if explain_match:
            result["explanation"] = explain_match.group(1).strip()[:500]

        return json.dumps(result)

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

        try:
            answer = json.loads(parsed_answer)
        except (json.JSONDecodeError, TypeError):
            return EvalResult(
                is_correct=False,
                score=0.0,
                details={"error": "Could not parse error recovery from response"},
            )

        # --- Error detection (0.2) ---
        ref_error = ref.get("error_detected", True)
        ans_error = answer.get("error_detected", False)
        detection_score = 1.0 if ans_error == ref_error else 0.0

        # --- Root cause / diagnosis (0.3) ---
        ref_diagnosis_keywords = ref.get("diagnosis_keywords", [])
        ans_diagnosis = answer.get("diagnosis", "").lower()
        if ref_diagnosis_keywords:
            found = sum(
                1 for kw in ref_diagnosis_keywords if kw.lower() in ans_diagnosis
            )
            diagnosis_score = found / len(ref_diagnosis_keywords)
        else:
            diagnosis_score = 1.0 if ans_diagnosis else 0.0

        # --- Recovery action correct (0.35) ---
        ref_action = ref.get("expected_action", "")
        ref_action_keywords = ref.get("action_keywords", [])
        ans_action = answer.get("recovery_action", "").lower()

        if ref_action_keywords:
            found = sum(
                1 for kw in ref_action_keywords if kw.lower() in ans_action
            )
            action_score = found / len(ref_action_keywords)
        elif ref_action:
            if ref_action.lower() in ans_action:
                action_score = 1.0
            elif ans_action and any(
                word in ans_action for word in ref_action.lower().split()
            ):
                action_score = 0.5
            else:
                action_score = 0.0
        else:
            action_score = 1.0 if ans_action else 0.0

        # --- Explanation quality (0.15) ---
        ref_explanation_keywords = ref.get("explanation_keywords", [])
        all_text = (
            answer.get("explanation", "") + " " +
            answer.get("diagnosis", "") + " " +
            answer.get("recovery_action", "")
        ).lower()

        if ref_explanation_keywords:
            found = sum(
                1 for kw in ref_explanation_keywords if kw.lower() in all_text
            )
            explanation_score = found / len(ref_explanation_keywords)
        else:
            explanation_score = 1.0 if answer.get("explanation") else 0.5

        total = (
            0.2 * detection_score
            + 0.3 * diagnosis_score
            + 0.35 * action_score
            + 0.15 * explanation_score
        )

        return EvalResult(
            is_correct=total >= 0.99,
            score=round(total, 4),
            details={
                "detection_score": round(detection_score, 4),
                "diagnosis_score": round(diagnosis_score, 4),
                "action_score": round(action_score, 4),
                "explanation_score": round(explanation_score, 4),
                "error_detected": ans_error,
                "expected_error": ref_error,
                "diagnosis_keywords_found": [
                    kw for kw in ref_diagnosis_keywords if kw.lower() in ans_diagnosis
                ],
                "action_keywords_found": [
                    kw for kw in ref.get("action_keywords", [])
                    if kw.lower() in ans_action
                ],
            },
        )
