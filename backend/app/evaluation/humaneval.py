import re
import subprocess
import sys
import tempfile

from app.config import settings
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
        timeout = settings.CODE_EXEC_TIMEOUT_SECONDS

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=True) as f:
                f.write(full_code)
                f.flush()
                # sys.executable: bare "python" is missing on many systems.
                # -I isolates the child from env vars, user site-packages and
                # the CWD on sys.path.
                result = subprocess.run(
                    [sys.executable, "-I", f.name],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
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
                details={"error": f"Execution timed out after {timeout} seconds"},
            )
        except Exception as e:
            return EvalResult(
                is_correct=False,
                score=0.0,
                details={"error": f"Execution error: {str(e)}"},
            )
