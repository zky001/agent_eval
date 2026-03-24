from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class EvalResult:
    is_correct: bool
    score: float
    details: dict = field(default_factory=dict)


class BaseEvaluator(ABC):
    @abstractmethod
    def parse_answer(self, raw_response: str, metadata: dict | None = None) -> str:
        pass

    @abstractmethod
    def score(self, parsed_answer: str, reference_answer: str, metadata: dict | None = None) -> EvalResult:
        pass
