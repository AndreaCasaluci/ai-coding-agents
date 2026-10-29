"""Lab 03 — Tools: schemas, dispatch, and descriptions.

Run: python3 labs/L03_tools.py

Goal: see the exact JSON the model receives, watch every dispatch failure mode,
and see how a description changes tool selection.
"""

from __future__ import annotations

import json
import re

from _helpers import note, section, temp_ws

from mini_agent import ToolRegistry, Workspace, make_fs_tools, tool
from mini_agent.messages import Message


@tool(side_effect=True, needs_permission=True)
def deploy(env: str = "staging") -> str:
    """Deploy the current branch to an environment."""
    return f"deployed to {env}"


@tool(side_effect=True, needs_permission=True)
def rollback(service: str) -> str:
    """Roll back a service to its previous release."""
    return f"rolled back {service}"


def pick(task: str, registry: ToolRegistry) -> str:
    """A toy 'model': score task words against name + description."""
    words = {w for w in re.findall(r"[a-z]{4,}", task.lower())}
    best, score = "(none)", 0
    for t in registry:
        haystack = f"{t.name} {t.description}".lower()
        s = sum(1 for w in words if w in haystack)
        if s > score:
            best, score = t.name, s
    return best


def main() -> None:
    with temp_ws("tools") as tmp:
        ws = Workspace(tmp)
        registry = ToolRegistry(make_fs_tools(ws)).add(deploy, rollback)

        section("1. THE SCHEMA THE MODEL SEES")
        print(json.dumps(registry.get("read_file").schema(), indent=2))
        note("The description is prompt text. Write it for the model, not for autocomplete.")

        section("2. TOOL COUNT AND CONTEXT COST")
        from mini_agent.context import estimate_tokens

        payload = json.dumps(registry.schemas())
        print(f"  {len(registry)} tools -> {estimate_tokens(payload)} estimated tokens, every call")
        note("Tools are not free. A large registry is a permanent context tax.")

        section("3. DISPATCH FAILURE MODES")
        cases = [
            ("unknown tool", "does_not_exist", {}),
            ("missing argument", "read_file", {}),
            ("wrong type / extra key", "read_file", {"path": "a.py", "bogus": 1}),
            ("malformed JSON", "read_file", {"__parse_error__": "{not json"}),
        ]
        for label, name, args in cases:
            result = registry.dispatch(name, args)
            print(f"  {label:<24} ok={result.ok!s:<5} {result.content[:90]}")

        section("4. A TOOL THAT RAISES")
        @tool
        def divide(a: int, b: int) -> float:
            """Divide a by b."""
            return a / b

        result = ToolRegistry([divide]).dispatch("divide", {"a": 1, "b": 0})
        note(f"ok={result.ok} content={result.content!r}")
        note("The loop survives. The model sees the error and can adapt.")

        section("5. DESCRIPTIONS DRIVE SELECTION")
        vague = ToolRegistry([
            tool(name="query", description="Query things")(lambda text: text),
            tool(name="fetch", description="Fetch things")(lambda text: text),
        ])
        specific = ToolRegistry([
            tool(name="search_code", description="Search source files with a regex. Use for finding definitions and call sites.")(lambda text: text),
            tool(name="fetch_url", description="Download a web page over HTTP. Use for external documentation.")(lambda text: text),
        ])
        task = "search for the definition of parse_date in the code"
        print(f"  task: {task!r}")
        print(f"  vague descriptions    -> {pick(task, vague)}")
        print(f"  specific descriptions -> {pick(task, specific)}")
        note("Same model, same task. The description did the work.")

        section("6. SIDE EFFECTS ARE DECLARED, NOT GUESSED")
        for name in ("read_file", "write_file", "delete_file", "deploy"):
            t = registry.get(name)
            print(f"  {name:<14} side_effect={t.side_effect!s:<5} needs_permission={t.needs_permission}")
        note("The harness uses this metadata for approval; the model never sees it.")


if __name__ == "__main__":
    _ = Message
    main()
