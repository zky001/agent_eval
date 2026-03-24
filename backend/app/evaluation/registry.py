from app.evaluation.base import BaseEvaluator
from app.evaluation.custom import CustomEvaluator
from app.evaluation.gsm8k import GSM8KEvaluator
from app.evaluation.humaneval import HumanEvalEvaluator
from app.evaluation.mmlu import MMLUEvaluator


class EvaluatorRegistry:
    _evaluators: dict[str, type[BaseEvaluator]] = {
        "gsm8k": GSM8KEvaluator,
        "mmlu": MMLUEvaluator,
        "humaneval": HumanEvalEvaluator,
        "custom": CustomEvaluator,
    }

    @classmethod
    def get(cls, dataset_type: str) -> BaseEvaluator:
        evaluator_cls = cls._evaluators.get(dataset_type.lower())
        if evaluator_cls is None:
            # Fall back to custom evaluator
            evaluator_cls = CustomEvaluator
        return evaluator_cls()
