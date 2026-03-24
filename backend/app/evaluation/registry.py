from app.evaluation.api_interaction import APIInteractionEvaluator
from app.evaluation.base import BaseEvaluator
from app.evaluation.custom import CustomEvaluator
from app.evaluation.error_recovery import ErrorRecoveryEvaluator
from app.evaluation.gsm8k import GSM8KEvaluator
from app.evaluation.humaneval import HumanEvalEvaluator
from app.evaluation.instruction_following import InstructionFollowingEvaluator
from app.evaluation.mmlu import MMLUEvaluator
from app.evaluation.multi_step import MultiStepEvaluator
from app.evaluation.react import ReActEvaluator
from app.evaluation.tool_use import ToolUseEvaluator


class EvaluatorRegistry:
    _evaluators: dict[str, type[BaseEvaluator]] = {
        "gsm8k": GSM8KEvaluator,
        "mmlu": MMLUEvaluator,
        "humaneval": HumanEvalEvaluator,
        "custom": CustomEvaluator,
        "tool_use": ToolUseEvaluator,
        "multi_step": MultiStepEvaluator,
        "react": ReActEvaluator,
        "instruction_following": InstructionFollowingEvaluator,
        "api_interaction": APIInteractionEvaluator,
        "error_recovery": ErrorRecoveryEvaluator,
    }

    @classmethod
    def get(cls, dataset_type: str) -> BaseEvaluator:
        evaluator_cls = cls._evaluators.get(dataset_type.lower())
        if evaluator_cls is None:
            # Fall back to custom evaluator
            evaluator_cls = CustomEvaluator
        return evaluator_cls()
