"""Tools: schema, registry, dispatch.

Three ideas matter here and they carry over to every real agent:

1. A tool is a *description* (name + prose + JSON schema) plus a function.
   The model only ever sees the description. Bad descriptions cause bad calls.
2. Dispatch is a lookup, not magic. Unknown tool names and malformed
   arguments are data errors, not crashes.
3. Tool results go back into the context window. Size them deliberately.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Callable, get_args, get_origin, get_type_hints

# JSON Schema types for the Python annotations we support.
_TYPES: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    fn: Callable[..., Any]
    # Advisory metadata for hooks and permissions. Not sent to the model.
    side_effect: bool = False
    needs_permission: bool = False

    def schema(self) -> dict[str, Any]:
        """The exact object handed to the model. Descriptions are prompt text."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def run(self, arguments: dict[str, Any]) -> "ToolResult":
        try:
            value = self.fn(**arguments)
            return ToolResult(ok=True, content=value if isinstance(value, str) else json.dumps(value, indent=2, default=str))
        except TypeError as exc:
            return ToolResult(ok=False, content=f"Invalid arguments for {self.name}: {exc}")
        except Exception as exc:  # tool failures must not kill the loop
            return ToolResult(ok=False, content=f"{type(exc).__name__}: {exc}")


@dataclass
class ToolResult:
    ok: bool
    content: str
    meta: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.content


def tool(
    fn: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    side_effect: bool = False,
    needs_permission: bool = False,
) -> Any:
    """Decorator turning a function into a :class:`Tool`.

    The schema is derived from the signature and type hints. Supported types:
    str, int, float, bool, list, dict, and ``X | None`` / ``Optional[X]``.
    Keep tool signatures flat — nested schemas are where models start failing.
    """

    def wrap(f: Callable[..., Any]) -> Tool:
        hints = get_type_hints(f)
        params = list(inspect.signature(f).parameters.values())
        properties: dict[str, Any] = {}
        required: list[str] = []

        for p in params:
            if p.name in {"self", "cls"}:
                continue
            annotation = hints.get(p.name, str)
            prop = _schema_for(annotation)
            if p.default is inspect.Parameter.empty:
                required.append(p.name)
            else:
                prop["default"] = p.default
            properties[p.name] = prop

        return Tool(
            name=name or f.__name__,
            description=(description or inspect.getdoc(f) or "").strip(),
            parameters={"type": "object", "properties": properties, "required": required},
            fn=f,
            side_effect=side_effect,
            needs_permission=needs_permission,
        )

    return wrap(fn) if fn is not None else wrap


def _schema_for(annotation: Any) -> dict[str, Any]:
    origin = get_origin(annotation)
    if origin is not None:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if origin in (list, dict):
            return {"type": _TYPES[origin]}
        if len(args) == 1:  # Optional[X] / X | None
            return _schema_for(args[0])
    return {"type": _TYPES.get(annotation, "string")}


class ToolRegistry:
    """Name → Tool, plus the dispatch path used by the agent loop."""

    def __init__(self, tools: list[Tool] | None = None):
        self._tools: dict[str, Tool] = {}
        for t in tools or []:
            self.register(t)

    def register(self, t: Tool) -> Tool:
        if t.name in self._tools:
            raise ValueError(f"Duplicate tool name: {t.name}")
        self._tools[t.name] = t
        return t

    def add(self, *tools: Tool) -> "ToolRegistry":
        for t in tools:
            self.register(t)
        return self

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def __len__(self) -> int:
        return len(self._tools)

    def __iter__(self):
        return iter(self._tools.values())

    def schemas(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self._tools.values()]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        t = self.get(name)
        if t is None:
            return ToolResult(ok=False, content=f"Unknown tool `{name}`. Available: {', '.join(self._tools)}")
        if "__parse_error__" in arguments:
            return ToolResult(ok=False, content=f"Could not parse arguments for `{name}`: {arguments['__parse_error__']!r}")
        return t.run(arguments)
