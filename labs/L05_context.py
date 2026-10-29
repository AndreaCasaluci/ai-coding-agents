"""Lab 05 — Context engineering: budget, trim, compaction.

Run: python3 labs/L05_context.py

Goal: watch a transcript overflow, see what trimming keeps, and see exactly
what compaction loses.
"""

from __future__ import annotations

from _helpers import note, section

from mini_agent.context import (
    ContextBudget,
    estimate_tokens,
    summarize_naive,
    transcript_tokens,
)
from mini_agent.messages import Message, ToolCall


def build() -> list[Message]:
    messages = [Message("system", "You are a coding agent. " * 40)]
    messages.append(Message("user", "Fix the empty-date crash. Do not change the signature."))
    for i in range(8):
        messages.append(
            Message("assistant", f"Exploring hypothesis {i}. " + "reasoning " * 60,
                    [ToolCall(f"c{i}", "read_file", {"path": f"src/module_{i}.py"})])
        )
        messages.append(
            Message("tool", f"# module_{i}.py\n" + "def f():\n    pass\n" * 80,
                    tool_call_id=f"c{i}", name="read_file")
        )
        messages.append(Message("assistant", f"Hypothesis {i} rejected: the bug is not here. " * 20))
    messages.append(Message("user", "Reminder: the test expects ValueError, not None."))
    return messages


def main() -> None:
    messages = build()
    total = transcript_tokens(messages)

    section("1. ACCOUNTING")
    parts = {
        "system prompt": [m for m in messages if m.role == "system"],
        "user messages": [m for m in messages if m.role == "user"],
        "assistant text": [m for m in messages if m.role == "assistant"],
        "tool results": [m for m in messages if m.role == "tool"],
    }
    for label, subset in parts.items():
        print(f"  {label:<16} {transcript_tokens(subset):>6} tokens")
    print(f"  {'TOTAL':<16} {total:>6} tokens")
    note("Tool results dominate. That is almost always true in real sessions.")

    section("2. A BUDGET THAT DOES NOT FIT")
    budget = ContextBudget(max_tokens=4_000, reserve=800)
    print(f"  window={budget.max_tokens} reserve={budget.reserve} usable={budget.usable}")
    print(f"  transcript={total} fits={budget.fits(messages)}")
    note(f"usage: {budget.usage(messages):.0%} of usable budget")

    section("3. TRIM AT TURN BOUNDARIES")
    trimmed = budget.enforce(messages)
    print(f"  messages {len(messages)} -> {len(trimmed)}, tokens {total} -> {transcript_tokens(trimmed)}")
    print(f"  first kept: [{trimmed[1].role}] {trimmed[1].content[:100]}")
    print(f"  last kept : [{trimmed[-1].role}] {trimmed[-1].content[:100]}")
    note("Trimming drops whole turns. A tool result never survives without its call.")

    section("4. WHAT TRIM LOST")
    kept_text = " ".join(m.content for m in trimmed)
    for probe in ("Do not change the signature", "hypothesis 0", "hypothesis 5"):
        print(f"  {'kept' if probe in kept_text else 'LOST':<5} {probe!r}")
    note("The original constraint may be gone. That is why it belongs in the system prompt.")

    section("5. COMPACTION INSTEAD")
    compacted = budget.enforce(messages, compact=summarize_naive)
    print(f"  tokens {total} -> {transcript_tokens(compacted)}")
    summary = next(m for m in compacted if "compacted" in m.content)
    print("  summary:")
    for line in summary.content.splitlines()[:8]:
        print("   ", line)
    note("Kept: what was asked, which tools ran. Lost: file contents, rejected reasons.")

    section("6. THE TRADE")
    note("Trim: cheap, no extra model call, loses detail silently.")
    note("Compact: one extra call, keeps the shape, still loses detail — but says so.")
    note("Both are worse than not overflowing. Search narrowly; read ranges.")

    section("7. PREFIX STABILITY (CACHING)")
    base = [Message("system", "You are a coding agent. " * 200), Message("user", "task")]
    extended = base + [Message("assistant", "working " * 100)]
    print(f"  prefix tokens          : {transcript_tokens(base)}")
    print(f"  after appending a turn : {transcript_tokens(extended)}")
    note("The prefix is byte-identical, so a provider can cache it. Rewriting the")
    note("system prompt every turn invalidates the cache and costs full price.")


if __name__ == "__main__":
    main()
