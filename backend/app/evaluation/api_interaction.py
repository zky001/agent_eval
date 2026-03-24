import json
import re

from app.evaluation.base import BaseEvaluator, EvalResult


class APIInteractionEvaluator(BaseEvaluator):
    """Evaluates whether an agent can construct correct API calls."""

    def parse_answer(self, raw_response: str, metadata: dict | None = None) -> str:
        """Extract HTTP method, URL/endpoint, headers, and body from the response.

        Returns a JSON string with ``"method"``, ``"endpoint"``, ``"headers"``,
        and ``"body"`` fields.
        """
        result: dict = {
            "method": "",
            "endpoint": "",
            "headers": {},
            "body": None,
        }

        # Try parsing as JSON first
        try:
            parsed = json.loads(raw_response)
            if isinstance(parsed, dict):
                result["method"] = parsed.get("method", "")
                result["endpoint"] = parsed.get("endpoint", parsed.get("url", ""))
                result["headers"] = parsed.get("headers", {})
                result["body"] = parsed.get("body", parsed.get("data", None))
                return json.dumps(result)
        except (json.JSONDecodeError, TypeError):
            pass

        # Try to extract from curl command
        curl_match = re.search(r"curl\s+(.+?)(?:\n\n|\Z)", raw_response, re.DOTALL | re.IGNORECASE)
        if curl_match:
            curl_str = curl_match.group(0)
            # Method
            method_match = re.search(r"-X\s+(\w+)", curl_str)
            if method_match:
                result["method"] = method_match.group(1).upper()
            elif re.search(r"-d\s+|--data", curl_str):
                result["method"] = "POST"
            else:
                result["method"] = "GET"

            # URL
            url_match = re.search(r"""(?:curl\s+.*?['"]?(https?://[^\s'"]+|/[^\s'"]+)['"]?)""", curl_str)
            if url_match:
                result["endpoint"] = url_match.group(1)

            # Headers
            for hdr in re.finditer(r'-H\s+["\']([^"\']+)["\']', curl_str):
                parts = hdr.group(1).split(":", 1)
                if len(parts) == 2:
                    result["headers"][parts[0].strip()] = parts[1].strip()

            # Body
            body_match = re.search(r"""(?:-d|--data(?:-raw)?)\s+['"](.+?)['"]""", curl_str, re.DOTALL)
            if body_match:
                try:
                    result["body"] = json.loads(body_match.group(1))
                except (json.JSONDecodeError, TypeError):
                    result["body"] = body_match.group(1)

            return json.dumps(result)

        # Try to extract HTTP-style request line
        http_match = re.search(
            r"(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+((?:https?://)?/?\S+)",
            raw_response,
            re.IGNORECASE,
        )
        if http_match:
            result["method"] = http_match.group(1).upper()
            result["endpoint"] = http_match.group(2)

        # Try to find headers block
        header_matches = re.findall(r"([A-Za-z][\w-]+)\s*:\s*(.+?)(?:\n|$)", raw_response)
        for key, value in header_matches:
            key_lower = key.lower()
            if key_lower in (
                "content-type", "authorization", "accept", "x-api-key",
                "user-agent", "cache-control",
            ):
                result["headers"][key] = value.strip()

        # Try to find JSON body in response
        json_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", raw_response, re.DOTALL)
        if json_blocks and result["body"] is None:
            try:
                result["body"] = json.loads(json_blocks[-1])
            except (json.JSONDecodeError, TypeError):
                pass

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
                details={"error": "Could not parse API call from response"},
            )

        # --- Method correct (0.25) ---
        ref_method = ref.get("method", "").upper()
        ans_method = answer.get("method", "").upper()
        method_score = 1.0 if ref_method == ans_method else 0.0

        # --- Endpoint correct (0.25) ---
        ref_endpoint = ref.get("endpoint", "").rstrip("/").lower()
        ans_endpoint = answer.get("endpoint", "").rstrip("/").lower()
        if ref_endpoint == ans_endpoint:
            endpoint_score = 1.0
        elif ref_endpoint and ans_endpoint and (
            ref_endpoint.endswith(ans_endpoint) or ans_endpoint.endswith(ref_endpoint)
        ):
            # Partial credit: path matches but host may differ
            endpoint_score = 0.8
        else:
            endpoint_score = 0.0

        # --- Required headers present (0.25) ---
        ref_headers = ref.get("required_headers", {})
        ans_headers = answer.get("headers", {})
        if ref_headers:
            # Normalise header keys to lowercase for comparison
            ans_headers_lower = {k.lower(): v for k, v in ans_headers.items()}
            matched_headers = 0
            for k, v in ref_headers.items():
                ans_v = ans_headers_lower.get(k.lower(), "")
                if ans_v.lower().strip() == str(v).lower().strip():
                    matched_headers += 1
                elif ans_v:
                    # Header present but wrong value: half credit
                    matched_headers += 0.5
            headers_score = matched_headers / len(ref_headers)
        else:
            headers_score = 1.0

        # --- Body/params correct (0.25) ---
        ref_body = ref.get("body", None)
        ans_body = answer.get("body", None)
        if ref_body is None:
            body_score = 1.0
        elif ans_body is None:
            body_score = 0.0
        elif isinstance(ref_body, dict) and isinstance(ans_body, dict):
            if ref_body:
                matched_fields = 0
                for k, v in ref_body.items():
                    if k in ans_body:
                        if str(ans_body[k]).strip().lower() == str(v).strip().lower():
                            matched_fields += 1
                        else:
                            matched_fields += 0.3  # key present, wrong value
                body_score = matched_fields / len(ref_body)
            else:
                body_score = 1.0
        else:
            body_score = 1.0 if str(ref_body) == str(ans_body) else 0.0

        total = 0.25 * method_score + 0.25 * endpoint_score + 0.25 * headers_score + 0.25 * body_score

        return EvalResult(
            is_correct=total >= 0.99,
            score=round(total, 4),
            details={
                "method_score": round(method_score, 4),
                "endpoint_score": round(endpoint_score, 4),
                "headers_score": round(headers_score, 4),
                "body_score": round(body_score, 4),
                "expected_method": ref_method,
                "actual_method": ans_method,
                "expected_endpoint": ref.get("endpoint", ""),
                "actual_endpoint": answer.get("endpoint", ""),
            },
        )
