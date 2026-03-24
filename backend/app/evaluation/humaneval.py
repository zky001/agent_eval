import re
import subprocess
import tempfile

from app.evaluation.base import BaseEvaluator, EvalResult


class HumanEvalEvaluator(BaseEvaluator):
    def parse_answer(self, raw_response: str, metadata: dict | None = None) -> str:
        # Extract code block between ```python and ```
        match = re.search(r"```python\s*\n(.*?)```", raw_response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try generic code block
        match = re.search(r"```\s*\n(.*?)```", raw_response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Return whole response if no code blocks found
        return raw_response.strip()

    def score(self, parsed_answer: str, reference_answer: str, metadata: dict | None = None) -> EvalResult:
        metadata = metadata or {}
        test_cases = metadata.get("test_cases", "")

        if not test_cases:
            # If no test cases, just check if code is syntactically valid
            try:
                compile(parsed_answer, "<string>", "exec")
                return EvalResult(
                    is_correct=True,
                    score=1.0,
                    details={"message": "Code compiles successfully, no test cases provided"},
                )
            except SyntaxError as e:
                return EvalResult(
                    is_correct=False,
                    score=0.0,
                    details={"error": f"Syntax error: {e}"},
                )

        # Combine code with test cases and run in subprocess
        full_code = f"{parsed_answer}\n\n{test_cases}"

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=True) as f:
                f.write(full_code)
                f.flush()
                result = subprocess.run(
                    ["python", f.name],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

            if result.returncode == 0:
                return EvalResult(
                    is_correct=True,
                    score=1.0,
                    details={"stdout": result.stdout, "message": "All tests passed"},
                )
            else:
                return EvalResult(
                    is_correct=False,
                    score=0.0,
                    details={"stderr": result.stderr, "stdout": result.stdout},
                )

        except subprocess.TimeoutExpired:
            return EvalResult(
                is_correct=False,
                score=0.0,
                details={"error": "Execution timed out after 5 seconds"},
            )
        except Exception as e:
            return EvalResult(
                is_correct=False,
                score=0.0,
                details={"error": f"Execution error: {str(e)}"},
            )
