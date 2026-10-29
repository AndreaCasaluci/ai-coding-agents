# 01 — LLMs, Tokens, Context

> **Objectives**
> - Explain what a model actually does on each call.
> - Convert between text, tokens, and cost.
> - Predict which tasks will fail because of context, not intelligence.

## What the model does

A language model is a function:

```
tokens_in → probability distribution over the next token
```

Everything else is scaffolding. It has no memory, no state, no ability to run
code, and no knowledge of what happened in the previous call unless that
previous call is in the text you send.

Three consequences you will feel every day:

1. **Statelessness.** The "conversation" is an illusion. Every call resends the
   whole transcript. The harness is the memory.
2. **Sampling.** Unless temperature is 0, the same prompt can produce different
   output. Even at 0, providers are not perfectly reproducible.
3. **No execution.** When a model "runs a test", it emitted a structured
   request. Something else ran the test and pasted the result back.

## Tokens

A token is a subword chunk. Rules of thumb:

| Content | Approx. chars/token |
|---|---|
| English prose | ~4 |
| Python / TypeScript | ~3 |
| JSON, minified | ~2.5 |
| Base64, hashes, minified JS | ~1.5–2 |
| Non-Latin scripts | ~1–2 |

So a 1,000-line Python file is roughly 10–15k tokens. A `package-lock.json` can
be 100k+ tokens on its own. **This is why "just read the whole repo" does not
work**, and why a single careless `cat` can end a session.

Count, do not guess:

```python
from mini_agent.context import estimate_tokens
estimate_tokens(open("mini_agent/agent.py").read())
```

## The context window

The window holds *everything* for one call:

```
┌──────────────────────────────────────────────────┐
│ system prompt          ~500–3,000 tokens         │
│ instruction files      ~200–5,000 tokens         │
│ tool schemas           ~100–500 tokens per tool  │
│ conversation history   grows every turn          │
│ tool results           the usual culprit         │
│ (reserved) next reply  ~1,000–8,000 tokens       │
└──────────────────────────────────────────────────┘
```

Two facts that surprise people:

- **Tool schemas count.** Forty tools is a few thousand tokens before you say
  anything, spent on every single call.
- **The reply needs room.** If you fill the window, the model has nowhere to
  answer. Hence `ContextBudget.reserve`.

### Context rot

Bigger windows do not mean you should use them. Models attend unevenly:
material in the middle of a long context is recalled worse than material at the
start or end, and irrelevant content measurably degrades reasoning. A 200k
window stuffed with 180k tokens of logs will often perform *worse* than a 20k
window with the right 5k.

Treat the window like RAM in 1995: precious, and the job of the harness is to
decide what is resident.

## Why agents fail, in model terms

| Symptom | Mechanism |
|---|---|
| "It invented a file that doesn't exist" | Plausible continuation, no verification step |
| "It forgot the instruction from 40 turns ago" | Instruction scrolled out or buried mid-context |
| "It kept editing the same line" | Stale read: its copy of the file is outdated |
| "It ignored the test failure" | Failure text was truncated or buried |
| "It got worse after I added docs" | Context rot; irrelevant material diluted attention |
| "It is slow and expensive" | Every turn resends everything; cost is quadratic in turns |

That last one is worth internalising. Cost per turn ≈ (context size) × (price
per token). Since context grows each turn, **a 30-turn session costs far more
than three 10-turn sessions**. Fresh sessions are a cost optimisation, not just
a hygiene habit.

## Determinism and temperature

- `temperature=0` reduces variance; it does not eliminate it.
- Coding agents usually run near 0 for edits, higher for brainstorming.
- Non-determinism is why **evals need repetition** (module 11). A single green
  run proves almost nothing.

## What this means for how you prompt

Because the model only sees the transcript:

- Say the constraint *now*, not "as I mentioned earlier".
- Put critical rules in the system prompt or an instruction file, where they
  are re-sent every call — not in turn 3 of the chat.
- Prefer showing the relevant code over describing it. Tokens spent on the
  actual file beat tokens spent on prose about the file.
- When output degrades, the first hypothesis is **context**, not capability.

## Lab

```bash
python3 labs/L01_tokens.py
```

You will measure real token counts for prose, code, and JSON, then watch a
budget reject a transcript and trim it.

## ✅ Checkpoint

1. Why does an agent's cost grow faster than linearly with turns?
2. A 4,000-line repo. Can you put it in a 128k window? Should you?
3. What does "stateless" mean for how you write follow-up messages?
4. Why is temperature 0 not a guarantee of reproducibility?
5. Name two things that consume context before the user says anything.

<details>
<summary>Answers</summary>

1. Every turn resends the full transcript, which itself grew.
2. Roughly yes (maybe 40–60k tokens), but no: rot, cost, and latency.
3. Restate what matters; the model has no memory outside the transcript.
4. Sampling hardware/kernel nondeterminism, batching, provider changes.
5. System prompt, instruction files, tool schemas.
</details>
