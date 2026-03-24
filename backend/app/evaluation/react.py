import json
import re

from app.evaluation.base import BaseEvaluator, EvalResult


class ReActEvaluator(BaseEvaluator):
    """Evaluates ReAct-style reasoning: Thought -> Action -> Observation loops."""

    def parse_answer(self, raw_response: str, metadata: dict | None = None) -> str:
        """Extract Thought/Action/Observation blocks from the response.

        Returns a JSON string with ``"thoughts"``, ``"actions"``,
        ``"observations"``, and ``"final_action"`` fields.
        """
        thought_pattern = re.compile(
            r"(?:^|\n)\s*Thought\s*[\d]*\s*[:]\s*(.*?)(?=\n\s*(?:Action|Observation|Thought|$))",
            re.IGNORECASE | re.DOTALL,
        )
        action_pattern = re.compile(
            r"(?:^|\n)\s*Action\s*[\d]*\s*[:]\s*(.*?)(?=\n\s*(?:Thought|Observation|Action|$))",
            re.IGNORECASE | re.DOTALL,
        )
        observation_pattern = re.compile(
            r"(?:^|\n)\s*Observation\s*[\d]*\s*[:]\s*(.*?)(?=\n\s*(?:Thought|Action|Observation|$))",
            re.IGNORECASE | re.DOTALL,
        )

        thoughts = [m.strip() for m in thought_pattern.findall(raw_response) if m.strip()]
        actions = [m.strip() for m in action_pattern.findall(raw_response) if m.strip()]
        observations = [m.strip() for m in observation_pattern.findall(raw_response) if m.strip()]

        final_action = actions[-1] if actions else ""

        result = {
            "thoughts": thoughts,
            "actions": actions,
            "observations": observations,
            "final_action": final_action,
        }
        return json.dumps(result)

    def score(
        self,
        parsed_answer: str,
        reference_answer: str,
        metadata: dict | None = None,
    ) -> EvalResult:
        metadata = metadata or {}
        min_reasoning_steps = metadata.get("min_reasoning_steps", 2)

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
                details={"error": "Could not parse ReAct structure from response"},
            )

        thoughts = answer.get("thoughts", [])
        actions = answer.get("actions", [])
        final_action = answer.get("final_action", "")
        expected_action = ref.get("expected_action", "")
        key_concepts = ref.get("key_concepts", [])

        # --- Thought-Action structure (0.3) ---
        # Reward for having thought/action pairs and meeting min reasoning steps
        num_steps = min(len(thoughts), len(actions))
        if num_steps == 0:
            structure_score = 0.0
        elif num_steps >= min_reasoning_steps:
            structure_score = 1.0
        else:
            structure_score = num_steps / min_reasoning_steps

        # Also check that thoughts and actions alternate properly (at least some exist)
        if thoughts and not actions:
            structure_score *= 0.5
        elif actions and not thoughts:
            structure_score *= 0.5

        # --- Correct final action (0.4) ---
        if expected_action:
            if final_action.strip().lower() == expected_action.strip().lower():
                action_score = 1.0
            elif expected_action.strip().lower() in final_action.strip().lower():
                action_score = 0.8
            elif final_action.strip().lower() in expected_action.strip().lower():
                action_score = 0.6
            else:
                # Check for partial matches (e.g., same function name)
                ref_func = re.match(r"(\w+)", expected_action)
                ans_func = re.match(r"(\w+)", final_action)
                if ref_func and ans_func and ref_func.group(1).lower() == ans_func.group(1).lower():
                    action_score = 0.4
                else:
                    action_score = 0.0
        else:
            action_score = 1.0 if final_action else 0.0

        # --- Reasoning quality: mentions key concepts (0.3) ---
        if key_concepts:
            all_thoughts_text = " ".join(thoughts).lower()
            all_text = (all_thoughts_text + " " + " ".join(actions).lower()).strip()
            found = sum(
                1 for concept in key_concepts if concept.lower() in all_text
            )
            reasoning_score = found / len(key_concepts)
        else:
            reasoning_score = 1.0 if thoughts else 0.0

        total = 0.3 * structure_score + 0.4 * action_score + 0.3 * reasoning_score

        return EvalResult(
            is_correct=total >= 0.99,
            score=round(total, 4),
            details={
                "structure_score": round(structure_score, 4),
                "action_score": round(action_score, 4),
                "reasoning_score": round(reasoning_score, 4),
                "num_thoughts": len(thoughts),
                "num_actions": len(actions),
                "final_action": final_action,
                "expected_action": expected_action,
                "key_concepts_found": [
                    c for c in key_concepts if c.lower() in " ".join(thoughts + actions).lower()
                ],
                "min_reasoning_steps": min_reasoning_steps,
            },
        )
