"""Lab 13 — Workflows: one-shot vs explore-plan-execute-verify.

Run: python3 labs/L13_workflows.py

Goal: run the same bug fix two ways and compare the diff, the turns, and the
evidence.
"""

from __future__ import annotations

from _helpers import note, section, temp_ws

from mini_agent import Agent, Message, ToolCall, Workspace, make_fs_tools, tool
from mini_agent.llm import ScriptedLLM

ORIGINAL = """\
from datetime import datetime

FMT = "%Y-%m-%d"

def parse_date(s):
    return datetime.strptime(s, FMT)

def helper():
    return 42
"""


def main() -> None:
    section("SETUP")
    note("Bug: parse_date('') raises a confusing ValueError from strptime.")
    note("Spec: it should raise ValueError('empty date'), and helper() must survive.")

    with temp_ws("workflow") as tmp:
        ws = Workspace(tmp)
        ws.write("src/dates.py", ORIGINAL)

        @tool
        def run_tests() -> str:
            """Run the test suite."""
            content = ws.read("src/dates.py")
            if "if not s" not in content:
                return "FAILED tests/test_dates.py::test_empty_string\n  expected ValueError('empty date')"
            if "def helper" not in content:
                return "FAILED tests/test_dates.py::test_helper\n  helper() is missing"
            return "2 passed in 0.01s"

        tools = make_fs_tools(ws) + [run_tests]

        section("1. ONE-SHOT: 'fix it'")
        # The model rewrites the whole file from its first guess. It never
        # reads the file, so it does not know helper() exists.
        oneshot = ScriptedLLM(
            Message("assistant", "Rewriting the function.", [
                ToolCall("c1", "write_file", {
                    "path": "src/dates.py",
                    "content": 'from datetime import datetime\n\nFMT = "%Y-%m-%d"\n\ndef parse_date(s):\n    if not s:\n        raise ValueError("empty date")\n    return datetime.strptime(s, FMT)\n',
                })
            ]),
            "Fixed parse_date.",
        )
        before = ws.read("src/dates.py")
        result = Agent(oneshot, tools, workspace=ws, max_turns=6).run("fix the empty-date bug")
        after = ws.read("src/dates.py")
        print(f"  turns={result.turns} calls={result.tool_calls}")
        print(f"  tests run by the agent? {'run_tests' in result.tool_calls}")
        print(f"  helper() preserved? {'def helper' in after}")
        print(f"  lines: {len(before.splitlines())} -> {len(after.splitlines())}")
        print(f"  verdict: {result.final}")

        section("2. STRUCTURED: explore -> plan -> test -> fix -> verify")
        ws.write("src/dates.py", ORIGINAL)
        structured = ScriptedLLM(
            Message("assistant", "Locating the function first.", [
                ToolCall("c1", "search", {"pattern": "def parse_date"})
            ]),
            Message("assistant", "Reading the whole file to see what else is there.", [
                ToolCall("c2", "read_file", {"path": "src/dates.py"})
            ]),
            Message("assistant", "Plan: add a guard at the top of parse_date. helper() is unrelated; leave it.", [
                ToolCall("c3", "edit_file", {
                    "path": "src/dates.py",
                    "old": "def parse_date(s):\n    return datetime.strptime(s, FMT)",
                    "new": "def parse_date(s):\n    if not s:\n        raise ValueError(\"empty date\")\n    return datetime.strptime(s, FMT)",
                })
            ]),
            Message("assistant", "Verifying.", [ToolCall("c4", "run_tests", {})]),
            "Added an empty-string guard; tests pass; helper() untouched.",
        )
        before = ws.read("src/dates.py")
        result = Agent(structured, tools, workspace=ws, max_turns=8).run("fix the empty-date bug")
        after = ws.read("src/dates.py")
        print(f"  turns={result.turns} calls={result.tool_calls}")
        print(f"  tests run by the agent? {'run_tests' in result.tool_calls}")
        print(f"  helper() preserved? {'def helper' in after}")
        print(f"  lines: {len(before.splitlines())} -> {len(after.splitlines())}")
        print(f"  verdict: {result.final}")

        section("3. COMPARE")
        note("Same task, same tools, same model. Different workflow.")
        note("One-shot: fewer turns, no evidence, silent data loss.")
        note("Structured: 2 extra turns, a plan, a test run, and a verifiable result.")
        note("The extra turns are cheaper than the review cycle they prevent.")

        section("4. THE SESSION SHAPE")
        note("1. EXPLORE  read-only, cheap, catches misunderstanding")
        note("2. PLAN     state the change and the files, no edits")
        note("3. EXECUTE  small edits, one concern")
        note("4. VERIFY   tests, types, diff")
        note("5. REPORT   what changed, what is unproven")

        section("5. WHEN TO TAKE OVER")
        note("Same failed attempt twice -> it will make it a third time.")
        note("Diff growing while tests stay red -> stop.")
        note("Edits outside the stated scope -> stop.")
        note("You cannot explain the change -> stop.")

    _ = ORIGINAL


if __name__ == "__main__":
    main()
