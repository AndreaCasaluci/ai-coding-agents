"""Lab 09 — Subagents: isolation, cost, and write races.

Run: python3 labs/L09_subagents.py

Goal: see what a subagent buys and what it costs, then reproduce the classic
parallel-write corruption.
"""

from __future__ import annotations

from _helpers import note, section, temp_ws

from mini_agent import Agent, Message, Workspace, make_fs_tools, run_parallel
from mini_agent.context import transcript_tokens
from mini_agent.llm import PolicyLLM

COUNTER = """\
count = 0

def increment():
    global count
    count += 1
    return count
"""


def main() -> None:
    with temp_ws("subagents") as tmp:
        ws = Workspace(tmp)
        ws.write("src/counter.py", COUNTER)
        ws.write("src/auth.py", "def login(user):\n    return user\n")

        seen: list[str] = []
        seen_roles: list[list[str]] = []

        # A stateless stand-in model. Real children get their own model calls.
        def policy(messages, tools):
            task = messages[-1].content
            seen.append(task)
            seen_roles.append([m.role for m in messages])
            if "security" in task:
                return Message("assistant", "Findings: src/auth.py:1 login() accepts any user. No other issues.")
            if "tests" in task:
                return Message("assistant", "There are no test files in this repo.")
            return Message("assistant", "ok")

        parent = Agent(PolicyLLM(policy), make_fs_tools(ws), workspace=ws)

        section("1. FAN OUT (READ-ONLY)")
        jobs = {
            "security": "security audit: find auth issues. Report file:line. Do not edit.",
            "tests": "test audit: list untested modules. Do not edit.",
        }
        results = run_parallel(parent, jobs)

        for name, result in results.items():
            print(f"  [{name}] turns={result.turns} tokens={result.tokens}")
            print(f"           {result.summary}")

        section("2. WHAT THE PARENT KEEPS")
        print(f"  child tasks seen by the model: {len(seen)}")
        print(f"  summaries held by the parent : {sum(len(r.summary) for r in results.values())} chars")
        print(f"  tokens in those summaries    : {transcript_tokens([Message('user', r.summary) for r in results.values()])}")
        note("The parent never sees the child's transcript. That is the point.")
        note("And the cost: it cannot verify anything the child did not cite.")

        section("3. CHILD CONTEXT IS FRESH")
        # Each child started from system + user only; no parent history leaked.
        print(f"  roles seen by the model, per child call: {seen_roles[:2]}")
        note("Two messages: system + the task. No parent history, no prior turns.")
        note("A child cannot ask a clarifying question. Its task must be self-contained.")

        section("4. THE WRITE RACE")
        ws.write("src/counter.py", COUNTER)
        a_read = ws.read("src/counter.py")   # agent A reads v1
        b_read = ws.read("src/counter.py")   # agent B reads v1

        ws.write("src/counter.py", a_read + "\n# change from A\n")
        ws.write("src/counter.py", b_read + "\n# change from B\n")

        final = ws.read("src/counter.py")
        print(f"  A's change present? {'change from A' in final}")
        print(f"  B's change present? {'change from B' in final}")
        note("B wrote a stale copy. A's work is gone, silently.")

        section("5. SERIALISED WRITES")
        ws.write("src/counter.py", COUNTER)
        # A writes, then B re-reads before writing.
        ws.write("src/counter.py", ws.read("src/counter.py") + "\n# change from A\n")
        ws.write("src/counter.py", ws.read("src/counter.py") + "\n# change from B\n")
        final = ws.read("src/counter.py")
        print(f"  A's change present? {'change from A' in final}")
        print(f"  B's change present? {'change from B' in final}")
        note("Serialise writes, or give each worker its own worktree and merge.")

        section("6. THE REVIEW PATTERN")
        note("implementer writes a diff")
        note("reviewer reads it cold (fresh context, read-only) and cites file:line")
        note("implementer addresses findings")
        note("The reviewer's value is not knowing why the change was made.")

        section("7. WHEN NOT TO DELEGATE")
        note("The parent needs the raw evidence (diff, test output) -> keep inline.")
        note("The task needs shared, evolving state -> keep inline.")
        note("The subtask is one function -> the delegation costs more than it saves.")


if __name__ == "__main__":
    main()
