"""Command line entry point: ``python3 -m mini_agent "task"``."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .agent import build_agent
from .context import transcript_tokens


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mini_agent",
        description="A small coding agent. Offline by default (scripted model).",
    )
    parser.add_argument("task", nargs="?", help="What you want the agent to do")
    parser.add_argument("--root", default=".", help="Workspace root (default: .)")
    parser.add_argument("--max-turns", type=int, default=20)
    parser.add_argument("--budget", type=int, default=32_000, help="Context budget in estimated tokens")
    parser.add_argument("--read-only", action="store_true", help="Refuse all writes")
    parser.add_argument("--no-skills", action="store_true")
    parser.add_argument("--audit", default=".mini_agent/audit.log", help="Audit log path ('' to disable)")
    parser.add_argument("--provider", choices=["mock", "openai"], default=os.environ.get("MINI_AGENT_PROVIDER", "mock"))
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print the full run result as JSON")
    parser.add_argument("--transcript", action="store_true", help="Print the full message transcript")
    args = parser.parse_args(argv)

    if not args.task:
        parser.print_help()
        return 2

    os.environ["MINI_AGENT_PROVIDER"] = args.provider

    agent = build_agent(
        root=Path(args.root),
        max_turns=args.max_turns,
        budget_tokens=args.budget,
        read_only=args.read_only,
        with_skills=not args.no_skills,
        audit_path=Path(args.audit) if args.audit else None,
        verbose=args.verbose,
    )

    print(f"workspace : {agent.workspace.root}")
    print(f"model     : {type(agent.llm).__name__}")
    print(f"tools     : {', '.join(t.name for t in agent.tools)}")
    if len(agent.skills):
        print(f"skills    : {', '.join(agent.skills.skills)}")
    print()

    result = agent.run(args.task)

    print(result.final)
    print()
    print(f"[{result.stopped_reason}] turns={result.turns} tokens~{result.tokens} calls={len(result.tool_calls)}")

    if args.transcript:
        print("\n--- transcript ---")
        print(result.transcript())
    if args.json:
        print(
            json.dumps(
                {
                    "final": result.final,
                    "stopped_reason": result.stopped_reason,
                    "turns": result.turns,
                    "tokens": result.tokens,
                    "tool_calls": result.tool_calls,
                    "error": result.error,
                },
                indent=2,
            )
        )
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
