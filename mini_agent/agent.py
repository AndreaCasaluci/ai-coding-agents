"""The agent loop.

This is the file to read twice. Everything else is a supporting cast.

    while turns < max_turns:
        reply = model(transcript, tools)
        if reply has no tool calls:  done
        for each call:
            hook(pre_tool) -> allow?
            result = dispatch(call)
            hook(post_tool)
            transcript += result
        transcript = budget.enforce(transcript)

Four things every real harness must get right, and most bugs live in:

1. **Transcript integrity.** Every assistant tool call needs exactly one tool
   result with the same id, in order. Violate this and the API rejects you.
2. **Termination.** A model that keeps calling tools will run forever. Bound
   turns *and* budget.
3. **Failure containment.** A tool error becomes a message, not an exception.
   A denied action becomes a message the model can react to.
4. **Observability.** You cannot debug what you did not record. Every turn is
   kept, including the denials.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from . import hooks as hook_events
from .context import ContextBudget, summarize_naive, transcript_tokens
from .hooks import HookBus
from .instructions import InstructionSet
from .llm import LLM
from .messages import Message, ToolCall
from .skills import SkillLibrary
from .tools import Tool, ToolRegistry
from .workspace import Workspace

SYSTEM_TEMPLATE = """You are a coding agent operating inside a workspace.

Workspace root: {root}

How to work:
- Inspect before you act. Read a file before editing it; never invent contents.
- Make the smallest change that solves the task. Do not refactor unasked.
- Prefer `edit_file` (unique-string replacement) over rewriting whole files.
- Verify your work: run tests or re-read the changed region before declaring done.
- If a tool is denied or fails, read the message and adapt. Do not retry blindly.
- When the task is complete, reply with a short summary of what changed.
{instructions}{skills}"""


@dataclass
class RunResult:
    final: str
    messages: list[Message]
    turns: int
    tokens: int
    stopped_reason: str  # completed | max_turns | error
    tool_calls: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.stopped_reason == "completed"

    def transcript(self) -> str:
        return "\n\n".join(m.text() for m in self.messages)


class Agent:
    def __init__(
        self,
        llm: LLM,
        tools: ToolRegistry | Sequence[Tool],
        *,
        workspace: Workspace | None = None,
        hooks: HookBus | None = None,
        skills: SkillLibrary | None = None,
        instructions: InstructionSet | None = None,
        budget: ContextBudget | None = None,
        max_turns: int = 20,
        name: str = "agent",
        system_extra: str = "",
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ):
        self.llm = llm
        self.tools = tools if isinstance(tools, ToolRegistry) else ToolRegistry(list(tools))
        self.workspace = workspace
        self.hooks = hooks or HookBus()
        self.skills = skills or SkillLibrary()
        self.instructions = instructions or InstructionSet()
        self.budget = budget or ContextBudget()
        self.max_turns = max_turns
        self.name = name
        self.system_extra = system_extra
        self.on_event = on_event or (lambda event, payload: None)

        # Attach skill loading as tools so disclosure is a model decision (L2).
        if len(self.skills):
            from .skill_tools import make_skill_tools

            for t in make_skill_tools(self.skills):
                if self.tools.get(t.name) is None:
                    self.tools.register(t)

    # -- construction helpers ---------------------------------------------
    def fork(self, name: str = "subagent") -> "Agent":
        """A sibling with the same configuration and a clean transcript."""
        return Agent(
            self.llm,
            self.tools,
            workspace=self.workspace,
            hooks=self.hooks,
            skills=self.skills,
            instructions=self.instructions,
            budget=self.budget,
            max_turns=self.max_turns,
            name=name,
            system_extra=self.system_extra,
            on_event=self.on_event,
        )

    def system_prompt(self) -> str:
        instructions = ""
        if self.instructions.items:
            instructions = "\n\n# Project instructions\n\n" + self.instructions.render()

        skills = ""
        if len(self.skills):
            skills = (
                "\n\n# Available skills\n\n"
                "Call `load_skill` before doing work that matches one of these:\n"
                + self.skills.catalog()
            )

        prompt = SYSTEM_TEMPLATE.format(
            root=self.workspace.root if self.workspace else "(none)",
            instructions=instructions,
            skills=skills,
        )
        if self.system_extra:
            prompt += "\n\n" + self.system_extra
        return prompt

    # -- the loop ----------------------------------------------------------
    def run(self, task: str, history: Sequence[Message] | None = None) -> RunResult:
        self.hooks.emit(hook_events.SESSION_START, {"agent": self.name, "task": task})

        prompt_hook = self.hooks.emit(hook_events.USER_PROMPT, {"task": task})
        task = prompt_hook.payload.get("task", task) if prompt_hook.allow else task

        messages: list[Message] = [Message("system", self.system_prompt())]
        messages.extend(history or [])
        messages.append(Message("user", task))

        tool_calls_made: list[str] = []
        turns = 0
        stopped = "max_turns"

        try:
            for turns in range(1, self.max_turns + 1):
                # Budget is enforced *before* the call, never after.
                messages = self.budget.enforce(messages, compact=summarize_naive)
                self.on_event("turn_start", {"turn": turns, "tokens": transcript_tokens(messages)})

                reply = self.llm.complete(messages, self.tools.schemas())
                messages.append(reply)

                if not reply.tool_calls:
                    stopped = "completed"
                    self.on_event("turn_end", {"turn": turns, "final": reply.content})
                    break

                for call in reply.tool_calls:
                    tool_calls_made.append(call.name)
                    messages.append(self._execute(call))

                self.on_event(
                    "turn_end",
                    {
                        "turn": turns,
                        "calls": [c.name for c in reply.tool_calls],
                        "tokens": transcript_tokens(messages),
                    },
                )
            else:
                turns = self.max_turns
                stopped = "max_turns"
        except Exception as exc:  # model or transport failure
            stopped = "error"
            error = f"{type(exc).__name__}: {exc}"
            self.hooks.emit(hook_events.SESSION_END, {"agent": self.name, "error": error})
            return RunResult(
                final=f"[agent error] {error}",
                messages=messages,
                turns=turns,
                tokens=transcript_tokens(messages),
                stopped_reason="error",
                tool_calls=tool_calls_made,
                error=error,
            )

        final = next((m.content for m in reversed(messages) if m.role == "assistant" and m.content), "")
        self.hooks.emit(hook_events.SESSION_END, {"agent": self.name, "stopped": stopped})
        return RunResult(
            final=final,
            messages=messages,
            turns=turns,
            tokens=transcript_tokens(messages),
            stopped_reason=stopped,
            tool_calls=tool_calls_made,
        )

    # -- one tool call, with hooks ----------------------------------------
    def _execute(self, call: ToolCall) -> Message:
        payload = {
            "agent": self.name,
            "tool": call.name,
            "arguments": dict(call.arguments),
            "side_effect": bool(getattr(self.tools.get(call.name), "side_effect", False)),
        }

        decision = self.hooks.emit(hook_events.PRE_TOOL, payload)
        if not decision.allow:
            self.on_event("tool_denied", {"tool": call.name, "reason": decision.reason})
            return Message("tool", f"DENIED: {decision.reason}", tool_call_id=call.id, name=call.name)

        payload = decision.payload or payload
        args = payload.get("arguments", {})

        if call.name in {"write_file", "edit_file", "delete_file"}:
            edit_payload = {"agent": self.name, "tool": call.name, "path": args.get("path", ""), **args}
            edit_decision = self.hooks.emit(hook_events.PRE_EDIT, edit_payload)
            if not edit_decision.allow:
                self.on_event("edit_denied", {"tool": call.name, "reason": edit_decision.reason})
                return Message("tool", f"DENIED: {edit_decision.reason}", tool_call_id=call.id, name=call.name)

        result = self.tools.dispatch(call.name, args)

        post = self.hooks.emit(
            hook_events.POST_TOOL,
            {"agent": self.name, "tool": call.name, "ok": result.ok, "content": result.content},
        )
        content = post.payload.get("content", result.content) if post.allow else f"BLOCKED BY POST-HOOK: {post.reason}"

        if call.name in {"write_file", "edit_file", "delete_file"} and result.ok:
            self.hooks.emit(hook_events.POST_EDIT, {"agent": self.name, "tool": call.name, "path": args.get("path", "")})

        self.on_event("tool", {"tool": call.name, "ok": result.ok, "content": content[:400]})
        return Message("tool", content, tool_call_id=call.id, name=call.name)


def build_agent(
    *,
    root: Path,
    llm: LLM | None = None,
    read_only: bool = False,
    max_turns: int = 20,
    budget_tokens: int = 32_000,
    with_skills: bool = True,
    audit_path: Path | None = None,
    verbose: bool = False,
) -> Agent:
    """Wire the standard harness: fs tools + instructions + skills + safe hooks."""
    from .hooks import deny_paths, redact_secrets
    from .instructions import discover
    from .llm import default_llm
    from .workspace import make_fs_tools

    root = Path(root).resolve()
    ws = Workspace(root, read_only=read_only)
    hooks = HookBus()

    # Deterministic guards: prompts cannot guarantee these.
    hooks.on(hook_events.PRE_EDIT, deny_paths((".env", ".git", "secrets", "node_modules")), name="protect-paths")
    hooks.on(hook_events.POST_TOOL, redact_secrets(), name="redact-secrets")

    if audit_path:
        from .hooks import audit_log

        audit_path = Path(audit_path)
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        handle = audit_path.open("a", encoding="utf-8")
        hooks.on(hook_events.PRE_TOOL, audit_log(handle), name="audit")

    skills = SkillLibrary.discover(root / "skills") if with_skills else SkillLibrary()
    instructions = discover(root)

    def emit(event: str, payload: dict[str, Any]) -> None:
        if verbose:
            print(f"  · {event}: {payload}")

    return Agent(
        llm or default_llm(),
        make_fs_tools(ws),
        workspace=ws,
        hooks=hooks,
        skills=skills,
        instructions=instructions,
        budget=ContextBudget(max_tokens=budget_tokens),
        max_turns=max_turns,
        on_event=emit,
    )
