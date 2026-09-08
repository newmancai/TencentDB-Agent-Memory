"""Portable copy of the existing qwen_openai_tool_bridge envelope translator.

No model/runtime imports; never repairs or executes generated tool calls.
"""
import json
import re
from typing import Any

TOOL_CALL = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)


def parse_tool_output(text: str, permitted_names: set[str], call_id: str) -> dict[str, Any]:
    calls = []
    matches = list(TOOL_CALL.finditer(text))
    residual = TOOL_CALL.sub("", text).strip()
    if "<tool_call>" in residual or "</tool_call>" in residual:
        raise ValueError("incomplete tool-call envelope")
    for index, match in enumerate(matches):
        value = json.loads(match.group(1))
        if not isinstance(value, dict) or set(value) != {"name", "arguments"}:
            raise ValueError("invalid tool-call object")
        if value["name"] not in permitted_names or not isinstance(value["arguments"], dict):
            raise ValueError("unknown tool or non-object arguments")
        calls.append({"id": f"call_{call_id}_{index}", "type": "function", "function": {
            "name": value["name"], "arguments": json.dumps(value["arguments"], ensure_ascii=False),
        }})
    message: dict[str, Any] = {"role": "assistant", "content": residual or None}
    if calls:
        message["tool_calls"] = calls
    return message
