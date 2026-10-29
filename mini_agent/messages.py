"""Message and tool-call types.

The whole agent conversation is a list of these. Everything else in the
harness is a function over that list. Keeping this file tiny is deliberate:
if you can hold the message model in your head, you can debug any agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class ToolCall:
    """A model's *request* to run a tool. The model does not run anything."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class Message:
    role: Role
    content: str = ""
    # Assistant messages may carry one or more tool requests.
    tool_calls: list[ToolCall] = field(default_factory=list)
    # Tool messages point back at the call they answer.
    tool_call_id: str | None = None
    name: str | None = None
    # Free-form bookkeeping (token counts, timestamps). Never sent to a model.
    meta: dict[str, Any] = field(default_factory=dict)

    def to_openai(self) -> dict[str, Any]:
        """Serialise to the Chat Completions shape used by most providers."""
        msg: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": _json(tc.arguments)},
                }
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.name:
            msg["name"] = self.name
        return msg

    @classmethod
    def from_openai(cls, raw: dict[str, Any]) -> "Message":
        calls = []
        for tc in raw.get("tool_calls") or []:
            fn = tc.get("function", {})
            calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=fn.get("name", ""),
                    arguments=_parse_json(fn.get("arguments", "{}")),
                )
            )
        return cls(
            role=raw.get("role", "assistant"),
            content=raw.get("content") or "",
            tool_calls=calls,
            tool_call_id=raw.get("tool_call_id"),
            name=raw.get("name"),
        )

    def text(self) -> str:
        """A flat, readable rendering — useful for transcripts and logs."""
        if self.role == "tool":
            return f"[tool:{self.name}] {self.content}"
        if self.tool_calls:
            calls = ", ".join(f"{c.name}({_json(c.arguments)})" for c in self.tool_calls)
            return f"[{self.role}] {self.content}\n  -> {calls}".strip()
        return f"[{self.role}] {self.content}".strip()


def _json(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _parse_json(text: str) -> dict[str, Any]:
    import json

    try:
        parsed = json.loads(text or "{}")
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except json.JSONDecodeError:
        # Malformed arguments are a real, common failure. Surface them as data
        # rather than crashing the loop; the tool dispatcher will reject them.
        return {"__parse_error__": text}
