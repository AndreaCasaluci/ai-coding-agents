"""A tiny eval runner.

An eval is three things: a task, a fresh environment, and a grader. Anything
else is a demo. The rules that make evals useful:

1. **Fresh state per case.** Reuse a workspace and you are testing the order
   of execution, not the agent.
2. **Grade the outcome, not the transcript.** "Did the tests pass?" beats
   "did it call read_file?" — the latter is brittle and rewards mimicry.
3. **A failing eval is a bug report.** Print enough detail to reproduce.
4. **Measure pass@k, not pass@1.** Non-deterministic systems need repetition
   before a number means anything.

This runner is sequential and in-process on purpose. Scale comes later.
"""

from __future__ import annotations

import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .agent import Agent, RunResult
    from .workspace import Workspace


@dataclass
class EvalCase:
    name: str
    task: str
    check: Callable[["RunResult", "Workspace"], "bool | str"]
    setup: Callable[["Workspace"], None] | None = None
    timeout_turns: int = 12


@dataclass
class EvalResult:
    name: str
    passed: bool
    detail: str
    turns: int
    tokens: int
    seconds: float
    transcript: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
            "turns": self.turns,
            "tokens": self.tokens,
            "seconds": round(self.seconds, 2),
        }


def run_evals(
    cases: list[EvalCase],
    make_agent: Callable[["Workspace"], "Agent"],
    seed: Path | None = None,
    keep_artifacts: bool = False,
) -> list[EvalResult]:
    """Run each case in its own temporary workspace.

    ``seed`` is an optional directory copied into every fresh workspace.
    """
    results: list[EvalResult] = []
    for case in cases:
        tmp = Path(tempfile.mkdtemp(prefix=f"eval-{case.name}-"))
        try:
            if seed:
                shutil.copytree(seed, tmp, dirs_exist_ok=True)
            from .workspace import Workspace

            ws = Workspace(tmp)
            if case.setup:
                case.setup(ws)
            agent = make_agent(ws)
            agent.max_turns = case.timeout_turns

            started = time.monotonic()
            result = agent.run(case.task)
            elapsed = time.monotonic() - started

            try:
                verdict = case.check(result, ws)
            except Exception as exc:  # a broken grader is a failed eval, not a crash
                verdict = f"grader error: {type(exc).__name__}: {exc}"

            passed = verdict is True
            detail = "ok" if verdict is True else (verdict if isinstance(verdict, str) else "failed")
            results.append(
                EvalResult(
                    name=case.name,
                    passed=passed,
                    detail=detail,
                    turns=result.turns,
                    tokens=result.tokens,
                    seconds=elapsed,
                    transcript=result.transcript(),
                )
            )
        finally:
            if keep_artifacts:
                print(f"[eval] artifacts kept at {tmp}")
            else:
                shutil.rmtree(tmp, ignore_errors=True)
    return results


def report(results: list[EvalResult]) -> str:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    lines = [f"# Eval report — {passed}/{total} passed", ""]
    lines.append("| case | result | detail | turns | tokens | s |")
    lines.append("|---|---|---|---|---|---|")
    for r in results:
        mark = "PASS" if r.passed else "FAIL"
        lines.append(f"| {r.name} | {mark} | {r.detail[:60]} | {r.turns} | {r.tokens} | {r.seconds:.1f} |")
    return "\n".join(lines)


def pass_at_k(run_once: Callable[[], bool], k: int = 3) -> float:
    """Fraction of k attempts that succeeded. The honest way to report."""
    return sum(1 for _ in range(k) if run_once()) / k
