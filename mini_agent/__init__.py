"""mini_agent — a small, readable coding-agent harness.

Read in this order:

    messages.py      the transcript model
    tools.py         schema, registry, dispatch
    workspace.py     the sandboxed filesystem
    context.py       budgets, trimming, compaction
    agent.py         the loop that ties it together
    instructions.py  AGENTS.md discovery
    skills.py        progressive disclosure
    hooks.py         deterministic lifecycle control
    subagents.py     isolated context
    mcp_lite.py      interoperable tool servers
    evals.py         measuring behaviour

Nothing here is production software. Everything here is a concept you can
point at.
"""

from .agent import Agent, RunResult, build_agent
from .context import ContextBudget, estimate_tokens, transcript_tokens
from .evals import EvalCase, EvalResult, report, run_evals
from .hooks import HookBus, HookResult
from .instructions import InstructionSet, discover
from .llm import HeuristicLLM, OpenAICompatLLM, PolicyLLM, ScriptedLLM, default_llm
from .messages import Message, ToolCall
from .skills import Skill, SkillLibrary, parse_skill
from .subagents import SubagentResult, run_parallel, run_subagent
from .tools import Tool, ToolRegistry, tool
from .workspace import Workspace, WorkspaceError, make_fs_tools

__version__ = "0.1.0"

__all__ = [
    "Agent",
    "RunResult",
    "build_agent",
    "ContextBudget",
    "estimate_tokens",
    "transcript_tokens",
    "EvalCase",
    "EvalResult",
    "report",
    "run_evals",
    "HookBus",
    "HookResult",
    "InstructionSet",
    "discover",
    "HeuristicLLM",
    "OpenAICompatLLM",
    "PolicyLLM",
    "ScriptedLLM",
    "default_llm",
    "Message",
    "ToolCall",
    "Skill",
    "SkillLibrary",
    "parse_skill",
    "SubagentResult",
    "run_parallel",
    "run_subagent",
    "Tool",
    "ToolRegistry",
    "tool",
    "Workspace",
    "WorkspaceError",
    "make_fs_tools",
]
