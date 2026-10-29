"""Lab 00 — Read a transcript.

Run: python3 labs/L00_orientation.py

Goal: see one complete agent run as data, and identify which parts came from
the model and which from the environment.
"""

from _helpers import note, section, temp_ws

from mini_agent import Agent, Message, ToolCall, Workspace, make_fs_tools
from mini_agent.context import transcript_tokens
from mini_agent.llm import ScriptedLLM

DATES = '''\
from datetime import datetime

FMT = "%Y-%m-%d"

def parse_date(s):
    return datetime.strptime(s, FMT)
'''


def main() -> None:
    with temp_ws("orientation") as tmp:
        ws = Workspace(tmp)
        ws.write("src/dates.py", DATES)

        # The scripted model stands in for a real one. Every Message here is
        # something a model could have produced.
        llm = ScriptedLLM(
            Message("assistant", "I'll locate parse_date.", [ToolCall("c1", "search", {"pattern": "def parse_date"})]),
            Message("assistant", "Reading the function.", [ToolCall("c2", "read_file", {"path": "src/dates.py"})]),
            Message(
                "assistant",
                "Empty input will raise a confusing ValueError from strptime. Add an explicit guard.",
                [
                    ToolCall(
                        "c3",
                        "edit_file",
                        {
                            "path": "src/dates.py",
                            "old": "def parse_date(s):\n    return datetime.strptime(s, FMT)",
                            "new": "def parse_date(s):\n    if not s:\n        raise ValueError(\"empty date\")\n    return datetime.strptime(s, FMT)",
                        },
                    )
                ],
            ),
            "Added an empty-string guard to parse_date.",
        )

        agent = Agent(llm, make_fs_tools(ws), workspace=ws, max_turns=8)
        result = agent.run("parse_date crashes on empty input. Fix it.")

        section("TRANSCRIPT")
        for i, message in enumerate(result.messages):
            print(f"\n--- message {i} ---")
            print(message.text())

        section("ANNOTATION")
        by_role: dict[str, int] = {}
        for message in result.messages:
            by_role[message.role] = by_role.get(message.role, 0) + 1
        note(f"messages by role: {by_role}")
        note(f"model calls (assistant messages): {by_role.get('assistant', 0)}")
        note(f"tool executions (tool messages):  {by_role.get('tool', 0)}")
        note(f"tool calls requested:             {len(result.tool_calls)}")
        note(f"estimated tokens at the end:      {transcript_tokens(result.messages)}")
        note(f"stopped because:                  {result.stopped_reason}")

        section("THE FILE AFTER THE RUN")
        print(ws.read("src/dates.py"))

        section("WHAT TO NOTICE")
        note("Assistant messages are guesses. Tool messages are observations.")
        note("The model never ran anything; the harness did, and pasted results back.")
        note("The run ended when an assistant message had no tool calls.")
        note("Turn count == assistant messages, not tool calls.")


if __name__ == "__main__":
    main()
