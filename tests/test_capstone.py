"""Tests for the capstone: the guard, the depth limit, and the evals."""

import tempfile
import unittest
from pathlib import Path

from capstone.repo_doctor import REPORT_NAME, build_doctor
from mini_agent import Message, ToolCall, Workspace
from mini_agent.llm import PolicyLLM


class CapstoneGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "app.py").write_text("def main():\n    return 0\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_write_outside_report_is_denied(self):
        ws = Workspace(self.root)
        agent = build_doctor(
            ws,
            llm=PolicyLLM(
                lambda m, t: Message("assistant", "hacking", [
                    ToolCall("c1", "write_file", {"path": "src/hacked.py", "content": "x"})
                ])
                if m[-1].role != "tool"
                else Message("assistant", "denied")
            ),
        )
        result = agent.run("write src/hacked.py")
        self.assertFalse((self.root / "src" / "hacked.py").exists())
        denied = [m for m in result.messages if m.role == "tool" and "DENIED" in m.content]
        self.assertEqual(len(denied), 1)
        self.assertIn("only REPORT.md", denied[0].content)

    def test_report_write_is_allowed(self):
        ws = Workspace(self.root)
        agent = build_doctor(
            ws,
            llm=PolicyLLM(
                lambda m, t: Message("assistant", "writing", [
                    ToolCall("c1", "write_file", {"path": REPORT_NAME, "content": "# ok\n"})
                ])
                if m[-1].role != "tool"
                else Message("assistant", "done")
            ),
        )
        result = agent.run("write the report")
        self.assertTrue((self.root / REPORT_NAME).exists())
        self.assertEqual(result.stopped_reason, "completed")

    def test_no_shell_tool_is_exposed(self):
        agent = build_doctor(Workspace(self.root))
        names = {t.name for t in agent.tools}
        self.assertNotIn("run_shell", names)
        self.assertNotIn("delete_file", names)
        self.assertIn("inventory", names)
        self.assertIn("delegate", names)

    def test_skill_is_available(self):
        agent = build_doctor(Workspace(self.root))
        self.assertEqual(len(agent.skills), 1)
        self.assertIn("repo-audit", agent.skills.skills)

    def test_nested_delegation_disabled(self):
        ws = Workspace(self.root)

        def eager(messages, tools):
            if messages[-1].role == "tool":
                return Message("assistant", "done: " + messages[-1].content[:120])
            return Message("assistant", "delegating", [
                ToolCall("c1", "delegate", {"name": "child", "task": "look around"})
            ])

        agent = build_doctor(ws, llm=PolicyLLM(eager))
        result = agent.run("delegate twice")
        self.assertIn("nested delegation is disabled", result.transcript())


class CapstoneEvalTests(unittest.TestCase):
    def test_all_evals_pass(self):
        from capstone.evals import run_all

        self.assertEqual(run_all(), 0)


if __name__ == "__main__":
    unittest.main()
