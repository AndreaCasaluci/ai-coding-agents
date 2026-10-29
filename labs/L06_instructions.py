"""Lab 06 — Instruction files and precedence.

Run: python3 labs/L06_instructions.py

Goal: see AGENTS.md discovery, precedence, and the difference between a vague
instruction and a specific one.
"""

from __future__ import annotations

from pathlib import Path

from _helpers import note, section, temp_ws

from mini_agent import Agent, Message, Workspace, discover, make_fs_tools
from mini_agent.llm import PolicyLLM

ROOT_MD = """\
# AGENTS.md

## Commands
- Test: `make test`   (starts a Postgres container)
- Lint: `ruff check .`

## Invariants
- Never commit to `main`.
- Money is integer cents. No floats.

## Traps
- `legacy/` is frozen. Do not refactor it.
"""

BACKEND_MD = """\
# backend/AGENTS.md

- Migrations go through `alembic revision`, never hand-written.
- The test DB is reset per test; do not share fixtures across modules.
"""


def main() -> None:
    with temp_ws("instructions") as tmp:
        root = Path(tmp)
        (root / "AGENTS.md").write_text(ROOT_MD)
        (root / "backend").mkdir()
        (root / "backend" / "AGENTS.md").write_text(BACKEND_MD)
        (root / "src").mkdir()

        section("1. DISCOVERY FROM THE ROOT")
        found = discover(root)
        for item in found.items:
            print(f"  {item.scope:<7} {item.path.relative_to(root)}")

        section("2. DISCOVERY FROM A SUBDIRECTORY")
        found_sub = discover(root, start=root / "backend")
        for item in found_sub.items:
            print(f"  {item.scope:<7} {item.path.relative_to(root)}")
        note("Root first, then the closer file. Specific overrides general.")

        section("3. WHAT THE MODEL ACTUALLY RECEIVES")
        agent = Agent(
            PolicyLLM(lambda m, t: Message("assistant", "ok")),
            make_fs_tools(Workspace(root)),
            workspace=Workspace(root),
            instructions=found_sub,
        )
        prompt = agent.system_prompt()
        start = prompt.find("# Project instructions")
        print(prompt[start:start + 700])
        note("Instructions are re-sent on every call. They do not scroll away.")

        section("4. VAGUE VS SPECIFIC")
        # A toy model that only obeys rules it can act on.
        def make_policy(rule_text: str):
            def policy(messages, tools):
                system = messages[0].content
                if "Use the logger in `obs/log.py`" in system:
                    return Message("assistant", "I will use obs.log.logger, not print().")
                if "Don't use print" in system:
                    return Message("assistant", "I will avoid print() … probably.")
                return Message("assistant", "No logging rule found; using print() like the surrounding code.")

            return PolicyLLM(policy)

        vague_md = "# AGENTS.md\n\n- Don't use print statements.\n"
        specific_md = "# AGENTS.md\n\n- Use the logger in `obs/log.py` (`from obs.log import logger`).\n"

        for label, text in (("vague", vague_md), ("specific", specific_md)):
            (root / "AGENTS.md").write_text(text)
            a = Agent(
                make_policy(text),
                make_fs_tools(Workspace(root)),
                workspace=Workspace(root),
                instructions=discover(root),
            )
            result = a.run("add logging to the checkout handler")
            print(f"  {label:<9} -> {result.final}")
        note("A prohibition says what not to do. The model fills the gap with a guess.")

        section("5. THE LADDER")
        note("instruction  → a suggestion, probabilistic")
        note("hook         → deterministic, in-process")
        note("test         → verifiable, survives the session")
        note("type system  → enforced by the compiler")
        note("Move a rule down this ladder when breaking it matters.")

        section("6. SIZE MATTERS")
        note(f"root AGENTS.md   : {len(ROOT_MD.splitlines())} lines")
        note(f"backend AGENTS.md: {len(BACKEND_MD.splitlines())} lines")
        note("Aim for 30–80 lines total. Longer files dilute the rules that matter.")


if __name__ == "__main__":
    main()
