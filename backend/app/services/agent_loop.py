"""Multi-turn agent execution against simulated tools.

The item defines the tool inventory and mocked responses; the model runs a
real Action -> Observation loop until it produces a final answer or hits the
turn budget. The full trajectory is recorded for display and scoring —
industry-standard agent evaluation scores the execution path, not just the
final output.
"""

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_MAX_TURNS = 6

AGENT_SYSTEM_TEMPLATE = """You are an AI agent that completes tasks by calling tools.

Available tools:
{tools_block}

Rules:
- To call a tool, respond with EXACTLY one line in this form (arguments as a single-line JSON object):
Action: tool_name({{"param": "value"}})
- After each Action you will receive an "Observation:" message with the tool result.
- Call one tool at a time. Never invent tool results yourself.
- When you have enough information to answer, respond with one line:
Final Answer: <your answer>"""

# Args must be a single-line JSON object per the system prompt
_ACTION_LINE_RE = re.compile(r"^\s*Action\s*:\s*([\w-]+)\s*\((.*)\)\s*$", re.IGNORECASE)
_ACTION_ANY_RE = re.compile(r"Action\s*:\s*([\w-]+)\s*\((.*)\)", re.IGNORECASE | re.DOTALL)
_FINAL_RE = re.compile(r"Final\s*Answer\s*:\s*(.+)", re.IGNORECASE | re.DOTALL)


@dataclass
class AgentLoopOutcome:
    final_answer: str | None
    trajectory: list[dict] = field(default_factory=list)
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def last_output(self) -> str:
        if not self.trajectory:
            return ""
        return self.trajectory[-1].get("model_output", "")


def build_system_prompt(tools: list[dict], extra_system: str | None = None) -> str:
    lines = []
    for tool in tools:
        params = tool.get("parameters", {})
        params_sig = ", ".join(f"{k}: {v}" for k, v in params.items()) if params else ""
        lines.append(f"- {tool.get('name')}({params_sig}): {tool.get('description', '')}")
    prompt = AGENT_SYSTEM_TEMPLATE.format(tools_block="\n".join(lines) or "(none)")
    if extra_system:
        prompt = f"{extra_system}\n\n{prompt}"
    return prompt


def parse_action(text: str) -> tuple[str, dict] | None:
    """Extract (tool_name, args) from a model turn, or None."""
    match = None
    for line in text.splitlines():
        line_match = _ACTION_LINE_RE.match(line)
        if line_match:
            match = line_match
    if match is None:
        match = _ACTION_ANY_RE.search(text)
    if match is None:
        return None

    tool_name = match.group(1)
    args_raw = match.group(2).strip()
    if not args_raw:
        return tool_name, {}
    try:
        args = json.loads(args_raw)
        if not isinstance(args, dict):
            args = {"value": args}
    except (json.JSONDecodeError, TypeError):
        args = {"_raw": args_raw}
    return tool_name, args


def execute_mock_tool(
    tools: list[dict],
    tool_name: str,
    args: dict,
    called_tools: set[str] | None = None,
) -> str:
    """Return the mocked observation for a tool call.

    A tool defines a static "response" and optionally ordered "responses"
    rules: {"when_args_contain": {param: substring},
            "when_called_after": "other_tool",   # optional, enables stateful
            "response": "..."}                    # flows like restart->recheck
    """
    called_tools = called_tools or set()
    tool = next((t for t in tools if t.get("name") == tool_name), None)
    if tool is None:
        known = ", ".join(t.get("name", "?") for t in tools)
        return f"Error: unknown tool '{tool_name}'. Available tools: {known}"

    for rule in tool.get("responses", []):
        prerequisite = rule.get("when_called_after")
        if prerequisite and prerequisite not in called_tools:
            continue
        conditions = rule.get("when_args_contain", {})
        if all(
            str(value).lower() in str(args.get(key, "")).lower()
            for key, value in conditions.items()
        ):
            return str(rule.get("response", ""))
    return str(tool.get("response", "OK"))


async def run_agent_loop(
    llm_client,
    prompt: str,
    item_metadata: dict,
    params: dict,
) -> AgentLoopOutcome:
    tools = item_metadata.get("tools", [])
    max_turns = int(item_metadata.get("max_turns", DEFAULT_MAX_TURNS))
    system = build_system_prompt(tools, extra_system=params.get("system"))
    loop_params = {**params, "system": system}

    outcome = AgentLoopOutcome(final_answer=None)
    messages: list[dict] = [{"role": "user", "content": prompt}]
    called_tools: set[str] = set()

    for turn in range(1, max_turns + 1):
        response = await llm_client.chat(messages, loop_params)
        outcome.latency_ms += response.latency_ms
        outcome.input_tokens += response.input_tokens
        outcome.output_tokens += response.output_tokens

        text = response.text or ""
        step: dict = {"turn": turn, "model_output": text}

        final_match = _FINAL_RE.search(text)
        action = parse_action(text)

        # A "Final Answer" ends the loop unless the model also emitted an
        # Action after it (planning text often mentions the final answer).
        if final_match and (
            action is None or final_match.start() > text.lower().rfind("action")
        ):
            outcome.final_answer = final_match.group(1).strip()
            step["final_answer"] = outcome.final_answer
            outcome.trajectory.append(step)
            break

        if action is not None:
            tool_name, args = action
            observation = execute_mock_tool(tools, tool_name, args, called_tools)
            called_tools.add(tool_name)
            step["action"] = {"tool": tool_name, "args": args}
            step["observation"] = observation
            outcome.trajectory.append(step)
            messages.append({"role": "assistant", "content": text})
            messages.append({"role": "user", "content": f"Observation: {observation}"})
            continue

        # Neither an action nor a final answer — nudge once per occurrence
        step["note"] = "no_action_or_final_answer"
        outcome.trajectory.append(step)
        messages.append({"role": "assistant", "content": text})
        messages.append(
            {
                "role": "user",
                "content": (
                    'Respond with either a tool call line "Action: tool_name({...})" '
                    'or a final line "Final Answer: ...".'
                ),
            }
        )

    return outcome
