import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from mini_agent.evals import EvalCase, report, run_evals
from mini_agent.mcp_lite import InProcessTransport, MCPClient, MCPServer, RPCError, StdioTransport
from mini_agent.subagents import run_subagent


class MCPTests(unittest.TestCase):
    def setUp(self):
        self.server = MCPServer("test")
        self.server.add_tool(
            {"name": "echo", "description": "Echo text", "parameters": {"type": "object"}},
            lambda args: args.get("text", ""),
        )
        self.server.resources["file:///readme"] = "hello"
        self.client = MCPClient(InProcessTransport(self.server))

    def test_handshake(self):
        info = self.client.initialize()
        self.assertEqual(info["serverInfo"]["name"], "test")

    def test_list_and_call_tool(self):
        self.client.initialize()
        tools = self.client.list_tools()
        self.assertEqual(tools[0]["name"], "echo")
        self.assertEqual(self.client.call_tool("echo", {"text": "hi"}), "hi")

    def test_unknown_method(self):
        with self.assertRaises(RPCError):
            self.client._request("does/not/exist")

    def test_unknown_tool_is_rpc_error(self):
        with self.assertRaises(RPCError):
            self.client.call_tool("nope", {})

    def test_resources(self):
        self.assertEqual(self.client.list_resources()[0]["uri"], "file:///readme")
        self.assertEqual(self.client.read_resource("file:///readme"), "hello")

    def test_stdio_transport_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "server.py"
            script.write_text(
                textwrap.dedent(
                    f"""
                    import sys
                    sys.path.insert(0, {str(Path.cwd())!r})
                    from mini_agent.mcp_lite import MCPServer
                    s = MCPServer("stdio-test")
                    s.add_tool({{"name": "ping", "description": "p", "parameters": {{}}}},
                               lambda a: "pong")
                    s.serve_stdio()
                    """
                )
            )
            transport = StdioTransport([sys.executable, str(script)])
            try:
                client = MCPClient(transport)
                self.assertEqual(client.initialize()["serverInfo"]["name"], "stdio-test")
                self.assertEqual(client.call_tool("ping", {}), "pong")
            finally:
                transport.close()


class SubagentTests(unittest.TestCase):
    def test_subagent_gets_fresh_context(self):
        from mini_agent.agent import Agent
        from mini_agent.llm import PolicyLLM
        from mini_agent.messages import Message
        from mini_agent.workspace import Workspace

        seen: list[int] = []

        def policy(messages, tools):
            seen.append(len(messages))
            return Message("assistant", "child answer")

        with tempfile.TemporaryDirectory() as tmp:
            ws = Workspace(tmp)
            parent = Agent(PolicyLLM(policy), [], workspace=ws)
            result = run_subagent(parent, "scout", "find the thing")
            self.assertEqual(result.summary, "child answer")
            self.assertTrue(result.ok)
            # Child transcript is system + user only: no parent history leaked.
            self.assertEqual(seen, [2])

    def test_parent_transcript_unaffected(self):
        from mini_agent.agent import Agent
        from mini_agent.llm import PolicyLLM
        from mini_agent.messages import Message
        from mini_agent.workspace import Workspace

        with tempfile.TemporaryDirectory() as tmp:
            parent = Agent(PolicyLLM(lambda m, t: Message("assistant", "ok")), [], workspace=Workspace(tmp))
            run_subagent(parent, "scout", "look around")
            result = parent.run("my task")
            self.assertEqual(len(result.messages), 3)  # system, user, assistant


class EvalTests(unittest.TestCase):
    def test_pass_and_fail_are_graded(self):
        from mini_agent.agent import Agent
        from mini_agent.llm import ScriptedLLM
        from mini_agent.messages import Message, ToolCall
        from mini_agent.workspace import make_fs_tools

        def make_agent(ws):
            # Fresh script per case: evals must not share model state.
            llm = ScriptedLLM(
                Message("assistant", "", [ToolCall("1", "write_file", {"path": "out.txt", "content": "x"})]),
                "done",
            )
            return Agent(llm, make_fs_tools(ws), workspace=ws)

        cases = [
            EvalCase(
                name="creates file",
                task="write it",
                check=lambda result, ws: ws.resolve("out.txt").exists() or "missing out.txt",
            ),
            EvalCase(
                name="fails on purpose",
                task="do nothing",
                check=lambda result, ws: False,
            ),
        ]
        results = run_evals(cases, make_agent)
        self.assertTrue(results[0].passed)
        self.assertFalse(results[1].passed)
        self.assertIn("1/2", report(results))


if __name__ == "__main__":
    unittest.main()
