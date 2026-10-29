import tempfile
import unittest

from mini_agent import Agent, Message, ToolCall
from mini_agent.context import ContextBudget, transcript_tokens
from mini_agent.hooks import PRE_TOOL, HookBus, HookResult
from mini_agent.llm import PolicyLLM, ScriptedLLM
from mini_agent.tools import ToolRegistry, tool
from mini_agent.workspace import Workspace, make_fs_tools


class LoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Workspace(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, llm, **kwargs):
        return Agent(llm, make_fs_tools(self.ws), workspace=self.ws, max_turns=kwargs.pop("max_turns", 5), **kwargs)

    def test_single_turn_completes(self):
        agent = self.make(ScriptedLLM("all done"))
        result = agent.run("say hi")
        self.assertEqual(result.stopped_reason, "completed")
        self.assertEqual(result.turns, 1)
        self.assertEqual(result.final, "all done")

    def test_tool_then_answer(self):
        llm = ScriptedLLM(
            Message("assistant", "reading", [ToolCall("1", "read_file", {"path": "a.txt"})]),
            "done",
        )
        self.ws.write("a.txt", "content")
        result = self.make(llm).run("read it")
        self.assertEqual(result.turns, 2)
        self.assertEqual(result.tool_calls, ["read_file"])
        self.assertIn("content", result.messages[-2].content)

    def test_tool_errors_are_returned_to_model(self):
        llm = ScriptedLLM(
            Message("assistant", "", [ToolCall("1", "read_file", {"path": "missing.txt"})]),
            "recovered",
        )
        result = self.make(llm).run("read missing")
        tool_msg = result.messages[-2]
        self.assertEqual(tool_msg.role, "tool")
        self.assertIn("No such file", tool_msg.content)
        self.assertEqual(result.final, "recovered")

    def test_max_turns_is_enforced(self):
        # A model that always calls a tool never terminates on its own.
        def policy(messages, tools):
            return Message("assistant", "", [ToolCall("x", "list_files", {"path": "."})])

        result = self.make(PolicyLLM(policy), max_turns=3).run("loop forever")
        self.assertEqual(result.stopped_reason, "max_turns")
        self.assertEqual(result.turns, 3)

    def test_llm_failure_is_captured(self):
        result = self.make(ScriptedLLM()).run("anything")
        self.assertEqual(result.stopped_reason, "error")
        self.assertIn("exhausted", result.error)

    def test_hook_denial_reaches_model(self):
        hooks = HookBus()
        hooks.on(PRE_TOOL, lambda p: HookResult(False, "nope"), name="deny-all")
        llm = ScriptedLLM(
            Message("assistant", "", [ToolCall("1", "list_files", {"path": "."})]),
            "understood",
        )
        result = self.make(llm, hooks=hooks).run("list")
        self.assertIn("DENIED: nope", result.messages[-2].content)

    def test_tool_call_ids_are_paired(self):
        llm = ScriptedLLM(
            Message("assistant", "", [ToolCall("abc", "list_files", {"path": "."})]),
            "done",
        )
        result = self.make(llm).run("list")
        assistant = next(m for m in result.messages if m.role == "assistant" and m.tool_calls)
        tool = next(m for m in result.messages if m.role == "tool")
        self.assertEqual(assistant.tool_calls[0].id, tool.tool_call_id)


class ContextTests(unittest.TestCase):
    def test_estimate_scales_with_text(self):
        self.assertGreater(transcript_tokens([Message("user", "x" * 4000)]), 500)

    def test_trim_keeps_system_and_recent_turn(self):
        messages = [Message("system", "sys")]
        for i in range(20):
            messages.append(Message("user", "u" * 500))
            messages.append(Message("assistant", "a" * 500))
        budget = ContextBudget(max_tokens=1000, reserve=100)
        out = budget.enforce(messages)
        self.assertEqual(out[0].role, "system")
        self.assertLessEqual(transcript_tokens(out), budget.usable + 50)
        # Must not start mid-turn (a tool result without its assistant call).
        self.assertNotEqual(out[1].role, "tool")

    def test_compaction_inserts_summary(self):
        messages = [Message("system", "sys")]
        for i in range(10):
            messages.append(Message("user", f"task {i} " + "x" * 500))
            messages.append(Message("assistant", "ok " + "y" * 500))
        budget = ContextBudget(max_tokens=800, reserve=100)
        out = budget.enforce(messages, compact=lambda ms: "summary here")
        self.assertTrue(any("compacted" in m.content for m in out))
        self.assertTrue(any("summary here" in m.content for m in out))

    def test_no_change_when_it_fits(self):
        messages = [Message("system", "sys"), Message("user", "hi")]
        budget = ContextBudget(max_tokens=10_000)
        self.assertEqual(budget.enforce(messages), messages)


if __name__ == "__main__":
    unittest.main()
