"""Lab 14 — Headless CI: budgets, read-only review, and a report.

Run: python3 labs/L14_ci.py

Goal: run the harness the way CI would — no human, hard limits, machine-readable
output — then see the permission layer refuse a push.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from _helpers import note, section, temp_ws

from mini_agent import Agent, Message, ToolCall, Workspace, make_fs_tools, tool
from mini_agent.context import ContextBudget
from mini_agent.hooks import PRE_TOOL, HookBus, HookResult
from mini_agent.llm import PolicyLLM


@dataclass
class JobResult:
    ok: bool
    report: dict
    turns: int
    tokens: int
    stopped: str


def review_policy(messages, tools):
    """A deterministic stand-in for a review model."""
    last = messages[-1]
    if last.role == "tool":
        findings = []
        if "eval(" in last.content:
            findings.append({"severity": "high", "file": "src/unsafe.py", "line": 2, "issue": "eval on input"})
        return Message("assistant", json.dumps({"findings": findings, "summary": "review complete"}))
    return Message("assistant", "Reading the risky file.", [
        ToolCall("c1", "read_file", {"path": "src/unsafe.py"})
    ])


def run_ci_job(ws: Workspace, max_turns: int = 6, budget_tokens: int = 8_000) -> JobResult:
    agent = Agent(
        PolicyLLM(review_policy),
        make_fs_tools(ws),
        workspace=ws,
        budget=ContextBudget(max_tokens=budget_tokens),
        max_turns=max_turns,
    )
    result = agent.run("review src/unsafe.py and return JSON findings")
    try:
        report = json.loads(result.final)
    except json.JSONDecodeError:
        report = {"findings": [], "summary": result.final, "parse_error": True}
    return JobResult(result.ok, report, result.turns, result.tokens, result.stopped_reason)


def main() -> None:
    with temp_ws("ci") as tmp:
        ws = Workspace(tmp)
        ws.write("src/unsafe.py", "def run(x):\n    return eval(x)\n")
        ws.write("src/app.py", "def main():\n    return 0\n")

        section("1. READ-ONLY REVIEW JOB")
        job = run_ci_job(ws)
        print(json.dumps(
            {"ok": job.ok, "turns": job.turns, "tokens": job.tokens, "stopped": job.stopped},
            indent=2,
        ))
        print(json.dumps(job.report, indent=2))
        note("Machine-readable output is the deliverable. Prose is for humans.")

        section("2. HARD LIMITS")
        tiny = run_ci_job(ws, max_turns=1)
        print(f"  max_turns=1 -> stopped={tiny.stopped} turns={tiny.turns}")
        note("A capped job fails cleanly instead of burning the CI budget.")
        note("Budget and turn limits are configuration, not suggestions.")

        section("3. THE REVIEWER MUST NOT WRITE")
        read_only_ws = Workspace(tmp, read_only=True)
        @tool(side_effect=True, needs_permission=True)
        def write_file_attempt(path: str, content: str) -> str:
            """A write that should never be reachable in review mode."""
            return read_only_ws.write(path, content)

        agent = Agent(
            PolicyLLM(lambda m, t: Message("assistant", "trying", [
                ToolCall("c1", "write_file_attempt", {"path": "fixed.py", "content": "x"})
            ]) if m[-1].role != "tool" else Message("assistant", "denied, stopping")),
            [write_file_attempt],
            workspace=read_only_ws,
            max_turns=3,
        )
        result = agent.run("fix the finding")
        print(f"  transcript: {[m.text()[:60] for m in result.messages[1:]]}")
        note("Read-only mode is enforced by the workspace, not by the prompt.")

        section("4. WRITE MODE: THE PUSH IS DENIED")
        hooks = HookBus()
        hooks.on(
            PRE_TOOL,
            lambda p: HookResult(False, "git push requires human approval")
            if p["tool"] == "run_shell" and "push" in str(p["arguments"])
            else None,
            name="no-push",
        )

        @tool(side_effect=True, needs_permission=True)
        def run_shell(command: str) -> str:
            """Run a shell command."""
            return f"ran: {command}"

        agent = Agent(
            PolicyLLM(lambda m, t: Message("assistant", "pushing", [
                ToolCall("c1", "run_shell", {"command": "git push origin main"})
            ]) if m[-1].role != "tool" else Message("assistant", "push denied; stopping")),
            [run_shell],
            workspace=ws,
            hooks=hooks,
            max_turns=3,
        )
        result = agent.run("push the fix")
        print(f"  transcript: {[m.text()[:70] for m in result.messages[1:]]}")
        note("Writes go to a branch; pushes need a human. Encode it in a hook.")

        section("5. WHAT TO AUTOMATE FIRST")
        note("1. diff review comments (read-only)")
        note("2. issue triage / labels")
        note("3. lint and type fixes (narrow, verifiable)")
        note("4. dependency updates (test-gated)")
        note("5. feature work (last, with a human in the loop)")

        section("6. METRICS THAT SURVIVE SCRUTINY")
        note("acceptance rate, revert rate, human edit rate")
        note("cycle time, cost per merged PR, escaped defects")
        note("not: lines generated, sessions started, self-reported time saved")


if __name__ == "__main__":
    main()
