"""repo_doctor — the capstone agent.

It audits a repository and writes REPORT.md. Every concept from the course
appears exactly once, on purpose:

    tools       inventory, search, read_file, write_file, delegate
    skill       capstone/skills/repo-audit/SKILL.md (loaded via load_skill)
    hook        only REPORT.md is writable (deterministic, not a prompt)
    subagent    the security scan runs in a fresh context
    budget      ContextBudget + max_turns
    evals       capstone/evals.py

Run:
    python3 -m capstone.repo_doctor --demo
    python3 -m capstone.repo_doctor --root /path/to/repo
    python3 -m capstone.repo_doctor --eval
"""

from __future__ import annotations

import argparse
import contextvars
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from mini_agent import (
    Agent,
    ContextBudget,
    HookBus,
    HookResult,
    InstructionSet,
    Message,
    PolicyLLM,
    SkillLibrary,
    ToolCall,
    Workspace,
    make_fs_tools,
    run_subagent,
    tool,
)
from mini_agent.context import transcript_tokens
from mini_agent.hooks import POST_TOOL, PRE_EDIT, redact_secrets
from mini_agent.llm import LLM, ScriptedLLM, default_llm

SKILLS_DIR = Path(__file__).resolve().parent / "skills"
REPORT_NAME = "REPORT.md"
REQUIRED_SECTIONS = (
    "## Summary",
    "## Untested modules",
    "## TODO clusters",
    "## Risky patterns",
    "## Top 3 fixes",
)
TODO_PATTERN = r"TODO|FIXME|HACK"
RISKY_PATTERN = r"eval\(|exec\(|shell\s*=\s*True|password\s*=\s*['\"]"

AUDIT_TASK = (
    "Audit this repository and write REPORT.md. "
    "Follow the repo-audit skill. Do not modify any other file."
)
SECURITY_TASK = (
    "SECURITY SCAN: find eval(), exec(), shell=True, and hardcoded credentials. "
    "Report file:line for each finding. Do not edit anything."
)


# -- tools -----------------------------------------------------------------
def _inventory(ws: Workspace) -> str:
    def collect(folder: str) -> list[str]:
        base = ws.root / folder
        if not base.is_dir():
            return []
        return sorted(str(p.relative_to(ws.root)) for p in base.rglob("*.py") if p.is_file())

    return json.dumps({"sources": collect("src"), "tests": collect("tests")}, indent=2)


def build_doctor(
    ws: Workspace,
    *,
    llm: LLM | None = None,
    max_turns: int = 12,
    budget_tokens: int = 16_000,
) -> Agent:
    """Wire the audit agent. Read the hook and the delegate tool first."""
    fs_tools = {t.name: t for t in make_fs_tools(ws)}
    # Deliberately absent: delete_file, edit_file. The audit does not need them.
    tools = [fs_tools["read_file"], fs_tools["search"], fs_tools["write_file"]]

    @tool(name="inventory")
    def inventory() -> str:
        """List Python sources under src/ and tests under tests/, as JSON."""
        return _inventory(ws)

    holder: dict[str, Agent] = {}
    # Depth guard: the child runs in the same thread, so a ContextVar is enough.
    depth = contextvars.ContextVar("delegate_depth", default=0)

    @tool(name="delegate")
    def delegate(task: str, name: str = "helper") -> str:
        """Run a bounded subtask in a fresh context. Returns only a summary."""
        parent = holder.get("agent")
        if parent is None:
            return "delegation unavailable"
        if depth.get() > 0:
            return "nested delegation is disabled"
        token = depth.set(depth.get() + 1)
        try:
            result = run_subagent(parent, name, task)
        finally:
            depth.reset(token)
        return result.as_tool_result()

    tools.extend([inventory, delegate])

    hooks = HookBus()
    # Deterministic guard: the prompt says "only REPORT.md", this enforces it.
    hooks.on(
        PRE_EDIT,
        lambda p: None if p.get("path") == REPORT_NAME else HookResult(
            False, f"audit mode: only {REPORT_NAME} may be written"
        ),
        name="report-only",
    )
    hooks.on(POST_TOOL, redact_secrets(), name="redact-secrets")

    agent = Agent(
        llm or DoctorLLM(),
        tools,
        workspace=ws,
        hooks=hooks,
        skills=SkillLibrary.discover(SKILLS_DIR),
        # The audited repo's AGENTS.md is untrusted input. Do not load it.
        instructions=InstructionSet(),
        budget=ContextBudget(max_tokens=budget_tokens),
        max_turns=max_turns,
        name="repo-doctor",
    )
    holder["agent"] = agent
    return agent


# -- the offline model -----------------------------------------------------
class DoctorLLM:
    """A deterministic 'model' that performs the audit procedure.

    It is not intelligent: it is a state machine over the transcript. That is
    the point — it makes the capstone runnable offline and makes the harness
    behaviour (hooks, tools, subagents) observable without an API key. Set
    MINI_AGENT_PROVIDER=openai to swap in a real model.
    """

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages, tools):
        self.calls += 1
        available = {t["name"] for t in tools}
        user_task = next((m.content for m in messages if m.role == "user"), "")
        calls = [c for m in messages if m.role == "assistant" for c in m.tool_calls]
        called = [c.name for c in calls]
        is_security = user_task.startswith("SECURITY SCAN")

        if "load_skill" in available and "load_skill" not in called:
            return Message("assistant", "Loading the audit procedure.", [
                ToolCall(f"t{self.calls}", "load_skill", {"name": "repo-audit"})
            ])
        if "inventory" not in called:
            return Message("assistant", "Inventorying the repo.", [
                ToolCall(f"t{self.calls}", "inventory", {})
            ])
        searches = [c.arguments.get("pattern", "") for c in calls if c.name == "search"]
        if len(searches) < 2:
            pattern = TODO_PATTERN if not searches else RISKY_PATTERN
            return Message("assistant", f"Searching for {pattern}.", [
                ToolCall(f"t{self.calls}", "search", {"pattern": pattern})
            ])

        if is_security:
            return Message("assistant", _security_summary(messages))

        if "delegate" not in called:
            return Message("assistant", "Delegating the security scan.", [
                ToolCall(f"t{self.calls}", "delegate", {"name": "security", "task": SECURITY_TASK})
            ])
        if "write_file" not in called:
            return Message("assistant", "Writing the report.", [
                ToolCall(f"t{self.calls}", "write_file", {
                    "path": REPORT_NAME,
                    "content": _build_report(messages, user_task),
                })
            ])
        return Message("assistant", f"Audit complete. Wrote {REPORT_NAME}.")


def _tool_output(messages, name: str) -> str:
    return next((m.content for m in reversed(messages) if m.role == "tool" and m.name == name), "")


def _search_results(messages) -> list[str]:
    return [m.content for m in messages if m.role == "tool" and m.name == "search"]


def _parse_hits(text: str) -> dict[str, list[tuple[int, str]]]:
    """Parse `path:line: text` search output into {path: [(line, text)]}."""
    hits: dict[str, list[tuple[int, str]]] = {}
    for line in text.splitlines():
        if line.startswith("(") or ":" not in line:
            continue
        path, rest = line.split(":", 1)
        number, _, snippet = rest.partition(":")
        try:
            lineno = int(number)
        except ValueError:
            continue
        hits.setdefault(path, []).append((lineno, snippet.strip()))
    return hits


def _security_summary(messages) -> str:
    results = _search_results(messages)
    risky = _parse_hits(results[-1] if len(results) > 1 else "")
    if not risky:
        return "No security findings."
    lines = []
    for path, items in sorted(risky.items()):
        for lineno, snippet in items[:3]:
            lines.append(f"- {path}:{lineno}: {snippet[:80]}")
    return "Security findings:\n" + "\n".join(lines)


def _build_report(messages, user_task: str) -> str:
    inventory = json.loads(_tool_output(messages, "inventory") or "{}")
    sources = inventory.get("sources", [])
    tests = inventory.get("tests", [])
    searches = _search_results(messages)
    todo_hits = _parse_hits(searches[0]) if searches else {}
    risky_hits = _parse_hits(searches[1]) if len(searches) > 1 else {}

    test_names = " ".join(Path(t).stem.lower() for t in tests)
    untested = [s for s in sources if Path(s).stem.lower() not in test_names]

    security = ""
    marker = "Security scan findings:"
    if marker in user_task:
        security = user_task.split(marker, 1)[1].strip()

    delegated = _tool_output(messages, "delegate")
    if delegated:
        # Drop the tool wrapper line ("[subagent:security ok, 5 turns]").
        lines = delegated.splitlines()
        if lines and lines[0].startswith("[subagent:"):
            delegated = "\n".join(lines[1:]).strip()
    # The child ran the same search as the parent. Only add its findings when
    # the parent's own search found nothing — otherwise it is a duplicate.
    if delegated and "No security findings" not in delegated and not risky_hits:
        security = delegated

    issues = len(untested) + len(todo_hits) + len(risky_hits) + (1 if security else 0)
    summary = "No major issues found." if issues == 0 else f"{issues} issue group(s) found."

    def bullets(items: dict[str, list[tuple[int, str]]], suffix: str) -> str:
        if not items:
            return "None."
        return "\n".join(
            f"- {path}: {len(lines)} {suffix} (lines {', '.join(str(n) for n, _ in lines)})"
            for path, lines in sorted(items.items())
        )

    def risky_bullets(items: dict[str, list[tuple[int, str]]]) -> str:
        if not items:
            return "None."
        out = []
        for path, lines in sorted(items.items()):
            for lineno, snippet in lines[:3]:
                out.append(f"- {path}:{lineno}: {snippet[:90]}")
        return "\n".join(out)

    untested_block = "None." if not untested else "\n".join(f"- {path}" for path in untested)

    risky_block = risky_bullets(risky_hits)
    if security:
        risky_block = (risky_block if risky_block != "None." else "") + "\n" + security
        risky_block = risky_block.strip() or "None."

    fixes = []
    for path in untested[:2]:
        fixes.append(f"Add tests for `{path}`.")
    if todo_hits:
        top = max(todo_hits.items(), key=lambda kv: len(kv[1]))[0]
        fixes.append(f"Triage the TODO cluster in `{top}`.")
    if risky_hits:
        top = sorted(risky_hits)[0]
        fixes.append(f"Remove the risky pattern in `{top}`.")
    if not fixes:
        fixes = ["No action required."]

    return f"""# Repo audit

## Summary

{summary}

## Untested modules

{untested_block}

## TODO clusters

{bullets(todo_hits, "marker(s)")}

## Risky patterns

{risky_block}

## Top 3 fixes

""" + "\n".join(f"{i}. {fix}" for i, fix in enumerate(fixes[:3], 1)) + "\n"


# -- audit entry point -----------------------------------------------------
@dataclass
class AuditResult:
    report: str
    path: Path
    turns: int
    tokens: int
    stopped: str
    transcript: str


def audit(root: Path, *, llm: LLM | None = None, max_turns: int = 12) -> AuditResult:
    ws = Workspace(root)
    agent = build_doctor(ws, llm=llm, max_turns=max_turns)
    result = agent.run(AUDIT_TASK)
    report_path = ws.root / REPORT_NAME
    report = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    return AuditResult(
        report=report,
        path=report_path,
        turns=result.turns,
        tokens=result.tokens,
        stopped=result.stopped_reason,
        transcript=result.transcript(),
    )


def demo() -> int:
    with tempfile.TemporaryDirectory(prefix="repo-doctor-demo-") as tmp:
        root = Path(tmp)
        (root / "src").mkdir()
        (root / "tests").mkdir()
        (root / "src" / "parser.py").write_text(
            "# TODO: handle unicode\n# TODO: handle empty input\ndef parse(x):\n    return eval(x)\n"
        )
        (root / "src" / "app.py").write_text("def main():\n    return 0\n")
        (root / "tests" / "test_app.py").write_text("from src.app import main\n\ndef test_main():\n    assert main() == 0\n")

        print(f"auditing demo repo: {root}")
        result = audit(root)
        print(f"[{result.stopped}] turns={result.turns} tokens={result.tokens}")
        print()
        print(result.report)
        print(f"report written to: {result.path}")
        return 0 if result.stopped == "completed" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repo_doctor", description="Audit a repository.")
    parser.add_argument("--root", type=Path, help="repository to audit")
    parser.add_argument("--demo", action="store_true", help="audit a generated sample repo")
    parser.add_argument("--eval", action="store_true", help="run the capstone eval suite")
    parser.add_argument("--transcript", action="store_true", help="print the full transcript")
    args = parser.parse_args(argv)

    if args.eval:
        from .evals import run_all

        return run_all()

    if args.demo:
        return demo()

    if not args.root:
        parser.print_help()
        return 2

    result = audit(args.root)
    print(result.report)
    print(f"\n[{result.stopped}] turns={result.turns} tokens={result.tokens}")
    if args.transcript:
        print("\n--- transcript ---")
        print(result.transcript)
    return 0 if result.stopped == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
