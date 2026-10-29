"""Lab 01 — Tokens and the context budget.

Run: python3 labs/L01_tokens.py

Goal: build intuition for how fast a context fills, and watch a budget reject
and trim a transcript.
"""

from __future__ import annotations

import json

from _helpers import ROOT, note, section

from mini_agent.context import ContextBudget, estimate_tokens, transcript_tokens
from mini_agent.llm import ScriptedLLM
from mini_agent.messages import Message

PROSE = (
    "An agent is a language model in a loop with tools inside an environment. "
    "The harness owns the transcript, the budget, and the guardrails. "
) * 20


def main() -> None:
    section("1. CHARS PER TOKEN, BY CONTENT TYPE")
    samples = {
        "prose": PROSE,
        "python": (ROOT / "mini_agent" / "agent.py").read_text(),
        "json (tool schemas)": json.dumps([{"name": "read_file", "description": "Read a file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}]),
    }
    for label, text in samples.items():
        tokens = estimate_tokens(text)
        print(f"  {label:<22} {len(text):>7} chars  {tokens:>7} tokens  {len(text) / tokens:>5.2f} chars/token")

    note("Code and JSON are denser than prose. Budgets are spent faster than you expect.")

    section("2. WHAT A TURN COSTS")
    system = Message("system", "You are a coding agent. " * 60)
    tool_result = Message("tool", "def parse_date(s):\n    return ...\n" * 300, tool_call_id="c1", name="read_file")
    print(f"  system prompt : {transcript_tokens([system]):>6} tokens")
    print(f"  one file read : {transcript_tokens([tool_result]):>6} tokens")
    note("A 300-line file is a few thousand tokens. Twenty of those is a session.")

    section("3. A TRANSCRIPT THAT DOES NOT FIT")
    messages = [Message("system", "You are a coding agent.")]
    for i in range(12):
        messages.append(Message("user", f"task {i}: " + "explore the repo " * 40))
        messages.append(Message("assistant", "working " * 80))
    before = transcript_tokens(messages)
    budget = ContextBudget(max_tokens=2_000, reserve=400)
    print(f"  budget        : {budget.max_tokens} (usable {budget.usable})")
    print(f"  before        : {before} tokens, fits={budget.fits(messages)}")

    trimmed = budget.enforce(messages)
    after = transcript_tokens(trimmed)
    print(f"  after trim    : {after} tokens, fits={budget.fits(trimmed)}")
    print(f"  messages      : {len(messages)} -> {len(trimmed)}")
    note(f"first kept message role: {trimmed[1].role!r} (never 'tool' — that would orphan a call)")

    section("4. COMPACTION INSTEAD OF TRIM")
    from mini_agent.context import summarize_naive

    compacted = budget.enforce(messages, compact=summarize_naive)
    print(f"  compacted     : {transcript_tokens(compacted)} tokens")
    for message in compacted[:2]:
        print(f"  [{message.role}] {message.content[:220]}")
    note("The summary keeps what was asked and which tools ran.")
    note("It loses exact file contents and the reasons hypotheses were rejected.")

    section("5. THE COST CURVE")
    note("Each turn resends the whole transcript, which grew last turn.")
    for turns in (5, 10, 20, 40):
        avg = 1_500 + turns * 400
        total = sum(avg for _ in range(turns))
        print(f"  {turns:>2} turns, ~{avg:>5} tokens/turn -> ~{total:>7} tokens sent in total")
    note("Quadratic-ish. Three 10-turn sessions are much cheaper than one 30-turn session.")


if __name__ == "__main__":
    # Keep the import above the fold for readers; used in section 4.
    _ = ScriptedLLM
    main()
