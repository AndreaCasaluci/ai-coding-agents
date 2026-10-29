# 05 — Context Engineering

> **Objectives**
> - Account for every token in a call.
> - Choose between stuffing, retrieval, and compaction.
> - Explain why more context often makes agents worse.

## The budget, concretely

```
usable = window - reserve_for_reply
```

With a 32k budget and a 4k reserve, you have 28k to spend. A typical turn:

| Item | Tokens |
|---|---|
| system prompt | 800 |
| AGENTS.md | 1,200 |
| 6 tool schemas | 900 |
| transcript so far | 12,000 |
| latest tool result | 8,000 |
| **total** | **22,900** |
| remaining | 5,100 |

That remaining number is the one to watch. When it approaches zero, the next
tool result gets truncated or the turn gets trimmed — and the model starts
"forgetting" things. Nothing is wrong with the model; the budget ran out.

## Three strategies

### 1. Stuffing

Put everything relevant in the prompt. Works when the corpus is small and
stable (a single file, a short spec). Fails at repo scale, and degrades quality
before it fails outright.

### 2. Retrieval

Fetch only what the task needs, on demand. This is what tools give you:
`search` then `read_file(start, end)` instead of `read_file(everything)`.

Retrieval quality dominates agent quality. An agent that greps well beats a
smarter model that reads the wrong file.

### 3. Compaction

When history outgrows the budget, replace old turns with a summary.

```
[system]
[summary of turns 1–14: explored dates module, found parse_date at
 src/dates.py:41, added guard, test_empty_string still failing]
[turn 15 …]
```

Compaction is **lossy by definition**. What survives depends on what the
summariser kept. Typical casualties: exact file contents, the reason a
hypothesis was rejected, the user's original wording.

The harness here marks compacted spans explicitly so the model knows it is
working from a summary:

```python
Message("user", "[compacted earlier conversation — summary, not verbatim]\n...")
```

Without that marker, the model treats the summary as ground truth and stops
re-reading the file.

## What belongs in the window

Priority order, highest first:

1. **The current task**, verbatim.
2. **The rules that must not be violated** (system prompt, instructions).
3. **The code being changed**, as narrowly as possible.
4. **Evidence**: test output, error messages, search hits.
5. **Recent conversation**, the last few turns.
6. **Background**: architecture notes, conventions.

And what does not:

- full directory listings when one glob would do,
- entire lockfiles, minified bundles, base64 blobs,
- logs from successful runs,
- duplicated instructions in three places,
- the model's own long reasoning from ten turns ago.

## Context rot

Models do not attend uniformly across a long window. Empirically:

- material at the start and end is recalled better than the middle,
- irrelevant content measurably degrades reasoning,
- very long contexts increase latency and cost superlinearly.

So the counter-intuitive rule: **a smaller, well-chosen context usually
produces better output than a larger, complete one.** If quality drops after
you added documentation, remove the documentation.

## Prompt caching

Providers can cache a stable prefix (system prompt + tools + early history) and
charge less for re-sending it. Two design implications:

- **Keep the prefix stable.** Changing the system prompt or tool order every
  turn invalidates the cache.
- **Append, do not rewrite.** History that only grows is cache-friendly;
  aggressive re-ordering is not.

This is a cost lever, not a quality lever, but it changes the economics of
long sessions substantially.

## Context engineering is the job

Most "make the agent smarter" work is actually:

| Symptom | Real fix |
|---|---|
| Reads the wrong files | Better search tool, better descriptions |
| Forgets constraints | Move them to the system prompt / AGENTS.md |
| Repeats failed attempts | Keep failures in context; do not trim them first |
| Gets confused by a big repo | Scope the workspace; add a subdirectory AGENTS.md |
| Slow and expensive | Fresh sessions; compaction; smaller tool results |

Notice that none of these is "use a bigger model".

## The subagent shortcut

The most effective context technique is often *not sending the context at all*.
Spawn a subagent with a clean window, let it burn 40k tokens exploring, and
bring back a 300-token summary. You trade fidelity for budget. Module 09 covers
when that trade is worth it.

## Lab

```bash
python3 labs/L05_context.py
```

You will build a transcript that overflows, watch it get trimmed at a turn
boundary, then watch compaction replace the dropped span with a summary — and
see exactly what information disappears.

🔬 **Break it:** set `reserve=0` and watch the model's reply get squeezed out.

## ✅ Checkpoint

1. Why does cost grow superlinearly with turns?
2. When is stuffing better than retrieval?
3. What is lost in compaction, typically?
4. Why mark a summary as a summary?
5. Why can adding documentation make an agent worse?

<details>
<summary>Answers</summary>

1. Each turn resends a transcript that has grown.
2. Small, stable corpora — one file, a short spec.
3. Exact contents, rejected hypotheses, original wording.
4. Otherwise the model treats it as verbatim truth and stops re-reading.
5. Context rot: irrelevant material dilutes attention and increases cost.
</details>
