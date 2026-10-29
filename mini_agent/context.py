"""Context budgeting, trimming, and compaction.

A context window is a fixed budget spent on every call. The harness decides
what occupies it. Three levers, in increasing order of violence:

* **Budget** — measure before you call, refuse to silently overflow.
* **Trim** — drop the oldest *complete turns*, keeping the system prompt and
  the most recent work.
* **Compact** — replace the dropped span with a summary. Lossy; say so in the
  summary so the model knows.

Token counts here are estimates (chars/4). Real tokenisers differ, especially
for code and non-Latin scripts. Estimates are fine for budgeting, never for
billing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from .messages import Message


def estimate_tokens(text: str) -> int:
    """Crude but useful: ~4 chars per token for prose, fewer for code."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def message_tokens(m: Message) -> int:
    total = estimate_tokens(m.content)
    for call in m.tool_calls:
        total += estimate_tokens(call.name) + estimate_tokens(str(call.arguments)) + 4
    return total + 4  # role/formatting overhead


def transcript_tokens(messages: Sequence[Message]) -> int:
    return sum(message_tokens(m) for m in messages)


@dataclass
class ContextBudget:
    max_tokens: int = 32_000
    # Space reserved for the model's next reply and its tool calls.
    reserve: int = 4_000

    @property
    def usable(self) -> int:
        return max(0, self.max_tokens - self.reserve)

    def fits(self, messages: Sequence[Message]) -> bool:
        return transcript_tokens(messages) <= self.usable

    def usage(self, messages: Sequence[Message]) -> float:
        return transcript_tokens(messages) / self.usable if self.usable else 1.0

    def enforce(
        self,
        messages: Sequence[Message],
        compact: Callable[[Sequence[Message]], str] | None = None,
    ) -> list[Message]:
        """Return a transcript that fits, trimming or compacting as needed.

        Trimming happens at *turn boundaries* (a user message) so an assistant
        tool-call is never separated from its tool result. A dangling tool call
        is an instant API error, and a classic harness bug.
        """
        if self.fits(messages):
            return list(messages)

        system = [m for m in messages if m.role == "system"]
        rest = [m for m in messages if m.role != "system"]

        # Find the oldest turn boundary that brings us under budget.
        cut = 0
        while cut < len(rest) and not self.fits(system + rest[cut:]):
            cut += 1
        while cut < len(rest) and rest[cut].role != "user":
            cut += 1
        if cut >= len(rest):
            # Even one turn overflows. Keep the most recent turn boundary so the
            # transcript stays structurally valid; the next call may still be
            # too large, and that is a real signal (shrink tool output instead).
            users = [i for i, m in enumerate(rest) if m.role == "user"]
            cut = users[-1] if users else 0

        dropped, kept = rest[:cut], rest[cut:]
        if not dropped:
            return list(messages)

        if compact is not None:
            summary = compact(dropped)
            note = Message(
                "user",
                "[compacted earlier conversation — summary, not verbatim]\n" + summary,
            )
            return system + [note] + kept

        note = Message("user", f"[{len(dropped)} earlier messages omitted to fit the context budget]")
        return system + [note] + kept


def summarize_naive(messages: Sequence[Message]) -> str:
    """A placeholder summariser. A real one is another model call.

    Note what it keeps: user requests and tool names. Note what it loses:
    exact file contents. That loss is the bug you will chase later.
    """
    lines: list[str] = []
    for m in messages:
        if m.role == "user":
            lines.append(f"- user asked: {m.content[:160]}")
        elif m.role == "assistant" and m.tool_calls:
            names = ", ".join(c.name for c in m.tool_calls)
            lines.append(f"- assistant called: {names}")
        elif m.role == "assistant" and m.content:
            lines.append(f"- assistant said: {m.content[:160]}")
    return "\n".join(lines[-20:]) or "(nothing notable)"
