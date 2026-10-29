"""Hooks: deterministic code bound to lifecycle events.

The mental model: a prompt is a *suggestion*, a hook is a *rule*. If an action
must never happen, or must always happen, it does not belong in a prompt — it
belongs in a hook (or a permission system, which is a specialised hook).

Events used by this harness:

    session_start   once, before the first model call
    user_prompt     the task text, before it enters the transcript
    pre_tool        before a tool runs — may block or rewrite arguments
    post_tool       after a tool runs — may redact or truncate the result
    pre_edit        before a file write/edit — may block
    post_edit       after a file write/edit
    session_end     once, after the loop finishes

Semantics that matter:
* `pre_*` hooks are **deny-by-default only if you configure them that way**.
  A hook that returns None abstains; the action proceeds.
* The first denial wins and stops the chain. Fail closed on hook errors when
  the hook is a safety control.
* Hooks see structured payloads, not strings. Regexing a prompt is not a hook.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

SESSION_START = "session_start"
USER_PROMPT = "user_prompt"
PRE_TOOL = "pre_tool"
POST_TOOL = "post_tool"
PRE_EDIT = "pre_edit"
POST_EDIT = "post_edit"
SESSION_END = "session_end"

ALL_EVENTS = (SESSION_START, USER_PROMPT, PRE_TOOL, POST_TOOL, PRE_EDIT, POST_EDIT, SESSION_END)


@dataclass
class HookResult:
    allow: bool = True
    reason: str = ""
    payload: dict[str, Any] | None = None  # replacement payload, if any


HookFn = Callable[[dict[str, Any]], HookResult | None]


@dataclass
class Hook:
    event: str
    fn: HookFn
    name: str = ""


@dataclass
class HookBus:
    hooks: dict[str, list[Hook]] = field(default_factory=dict)
    log: list[tuple[str, str]] = field(default_factory=list)

    def on(self, event: str, fn: HookFn | None = None, *, name: str = ""):
        """Register a hook. Usable as a decorator or a direct call."""
        if event not in ALL_EVENTS:
            raise ValueError(f"Unknown event {event!r}. Known: {', '.join(ALL_EVENTS)}")

        def register(f: HookFn) -> HookFn:
            self.hooks.setdefault(event, []).append(Hook(event, f, name or getattr(f, "__name__", "hook")))
            return f

        return register(fn) if fn is not None else register

    def emit(self, event: str, payload: dict[str, Any]) -> HookResult:
        """Run every hook for the event, threading payload mutations through."""
        current = payload
        for hook in self.hooks.get(event, []):
            self.log.append((event, hook.name))
            try:
                result = hook.fn(current)
            except Exception as exc:  # fail closed: a broken guard must not open the gate
                return HookResult(allow=False, reason=f"hook {hook.name} raised {type(exc).__name__}: {exc}")
            if result is None:
                continue
            if not result.allow:
                return HookResult(allow=False, reason=result.reason or f"blocked by {hook.name}", payload=current)
            if result.payload is not None:
                current = result.payload
        return HookResult(allow=True, payload=current)


# -- hooks you will actually want -----------------------------------------

def deny_paths(prefixes: tuple[str, ...], *, message: str = "protected path") -> HookFn:
    """Block any file tool touching a protected path."""

    def hook(payload: dict[str, Any]) -> HookResult | None:
        path = str(payload.get("path", ""))
        for prefix in prefixes:
            if path == prefix or path.startswith(prefix.rstrip("/") + "/"):
                return HookResult(False, f"{message}: {path}")
        return None

    return hook


def redact_secrets(patterns: tuple[str, ...] = (r"sk-[A-Za-z0-9]{16,}", r"ghp_[A-Za-z0-9]{20,}")) -> HookFn:
    """Scrub credentials out of tool output before the model sees them."""
    import re

    compiled = [re.compile(p) for p in patterns]

    def hook(payload: dict[str, Any]) -> HookResult | None:
        content = payload.get("content")
        if not isinstance(content, str):
            return None
        redacted = content
        for rx in compiled:
            redacted = rx.sub("[REDACTED]", redacted)
        if redacted == content:
            return None
        return HookResult(True, "redacted", {**payload, "content": redacted})

    return hook


def require_approval(approver: Callable[[dict[str, Any]], bool]) -> HookFn:
    """Turn any pre_tool payload into a yes/no question."""

    def hook(payload: dict[str, Any]) -> HookResult | None:
        if approver(payload):
            return None
        return HookResult(False, f"not approved: {payload.get('tool')}")

    return hook


def audit_log(handle) -> HookFn:
    """Append every event to an open text file. Cheap, boring, invaluable."""

    def hook(payload: dict[str, Any]) -> HookResult | None:
        handle.write(str(payload) + "\n")
        handle.flush()
        return None

    return hook
