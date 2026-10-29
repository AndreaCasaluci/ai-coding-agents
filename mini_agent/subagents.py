"""Subagents: separate runs with separate context windows.

Why spawn one at all? Because context is the scarce resource, not compute.

A subagent gets:
  * its own transcript (the parent's history does not leak in),
  * its own tool budget and turn limit,
  * a task statement written by the parent,
and returns **only a summary**. That is the entire point: 40k tokens of
exploration collapse into 300 tokens of conclusion.

The cost is equally real: the child cannot ask clarifying questions, cannot
see what the parent already learned, and can confidently return a wrong answer.
Use a subagent when the subtask is *bounded and verifiable*; keep it in the
parent when the work needs shared context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid a circular import at runtime
    from .agent import Agent, RunResult


@dataclass
class SubagentResult:
    name: str
    task: str
    summary: str
    ok: bool
    turns: int
    tokens: int
    tool_calls: list[str] = field(default_factory=list)

    def as_tool_result(self) -> str:
        status = "ok" if self.ok else "failed"
        return f"[subagent:{self.name} {status}, {self.turns} turns]\n{self.summary}"


def run_subagent(parent: "Agent", name: str, task: str) -> SubagentResult:
    """Run a task in an isolated context and return only its conclusion.

    The child shares the *workspace* (so edits persist) but not the transcript.
    That asymmetry is what makes parallel work possible.
    """
    child = parent.fork(name=name)
    result: "RunResult" = child.run(task)
    return SubagentResult(
        name=name,
        task=task,
        summary=result.final,
        ok=result.stopped_reason == "completed",
        turns=result.turns,
        tokens=result.tokens,
        tool_calls=result.tool_calls,
    )


def run_parallel(parent: "Agent", jobs: dict[str, str], max_workers: int = 4) -> dict[str, SubagentResult]:
    """Run several subagents concurrently against the same workspace.

    ⚠️ Concurrency + shared workspace = races. Only parallelise *read-only*
    investigations, or give each worker its own worktree. Lesson 9 has the
    longer discussion; the short version is that this function is honest about
    being unsafe for writes.
    """
    from concurrent.futures import ThreadPoolExecutor

    results: dict[str, SubagentResult] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(run_subagent, parent, name, task): name for name, task in jobs.items()}
        for future, name in futures.items():
            results[name] = future.result()
    return results
