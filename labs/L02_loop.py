"""Lab 02 — The loop: termination, recovery, and denial.

Run: python3 labs/L02_loop.py

Four scenarios, each a full run. Read the transcript, not just the summary.
"""

from _helpers import note, section, temp_ws

from mini_agent import Agent, Message, ToolCall, Workspace, make_fs_tools
from mini_agent.hooks import PRE_TOOL, HookBus, HookResult
from mini_agent.llm import PolicyLLM, ScriptedLLM


def show(result) -> None:
    for message in result.messages[1:]:
        print("   " + message.text().replace("\n", "\n   ")[:400])
    note(f"stopped={result.stopped_reason} turns={result.turns} calls={result.tool_calls}")


def main() -> None:
    with temp_ws("loop") as tmp:
        ws = Workspace(tmp)
        ws.write("app.py", "def add(a, b):\n    return a + b\n")
        tools = make_fs_tools(ws)

        section("SCENARIO 1 — clean two-turn task")
        llm = ScriptedLLM(
            Message("assistant", "Reading the file first.", [ToolCall("c1", "read_file", {"path": "app.py"})]),
            "The function is correct.",
        )
        show(Agent(llm, tools, workspace=ws, max_turns=5).run("Check app.py"))

        section("SCENARIO 2 — tool error, model recovers")
        llm = ScriptedLLM(
            Message("assistant", "Reading the test.", [ToolCall("c1", "read_file", {"path": "test_app.py"})]),
            Message("assistant", "No test file. Let me list instead.", [ToolCall("c2", "list_files", {"path": "."})]),
            "There is no test file; app.py only.",
        )
        show(Agent(llm, tools, workspace=ws, max_turns=6).run("Read test_app.py"))

        section("SCENARIO 3 — a model that never stops")
        # This policy always calls a tool, like a model stuck retrying.
        def stuck(messages, schemas):
            return Message("assistant", "Trying again.", [ToolCall("x", "list_files", {"path": "."})])

        result = Agent(PolicyLLM(stuck), tools, workspace=ws, max_turns=4).run("loop")
        show(result)
        note("Without max_turns this would run until the bill arrives.")

        section("SCENARIO 4 — a hook denies an action")
        hooks = HookBus()
        hooks.on(PRE_TOOL, lambda p: HookResult(False, "writes disabled in this session"), name="no-writes")
        llm = ScriptedLLM(
            Message("assistant", "Writing a file.", [ToolCall("c1", "write_file", {"path": "new.py", "content": "x"})]),
            "Understood — I cannot write here.",
        )
        result = Agent(llm, tools, workspace=ws, hooks=hooks, max_turns=5).run("create new.py")
        show(result)
        note("The denial is a message, not a crash. The model can choose another path.")

        section("WHAT TO NOTICE")
        note("A run is complete only when a reply has no tool calls.")
        note("Tool failures and denials both re-enter the loop as text.")
        note("max_turns is the difference between a bad session and an expensive one.")


if __name__ == "__main__":
    main()
