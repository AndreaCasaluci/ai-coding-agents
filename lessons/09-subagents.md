# 09 — Subagents & Orchestration

> **Objectives**
> - Decide when a subagent is worth its cost.
> - Explain the isolation trade-off in both directions.
> - Run parallel work without corrupting the workspace.

## The economics

A subagent is a **context compressor with a network call in the middle**.

```
parent context:  12,000 tokens
subagent run:    40,000 tokens of exploration
returned:           300 tokens of conclusion
```

You spent 40k tokens to save 40k tokens of parent context. That is only a win
if:

- the exploration is genuinely large (many files, many dead ends),
- the conclusion is compact and verifiable,
- the parent does not need the raw evidence.

If the parent needs the diff, the test output, or the reasoning, do the work
inline. A summary cannot be re-read.

## When to delegate

| Delegate | Keep inline |
|---|---|
| "Find every call site of X" | "Fix this one function" |
| "Audit this module for injection risks" | "Add a null check" |
| "Run the test suite and report failures" | "Make this test pass" |
| "Review this diff for bugs" | "Implement the feature" |
| Independent, read-only investigations | Anything with shared, evolving state |

The pattern that works best: **fan out for reading, serialise for writing.**

## Isolation, both directions

```
parent transcript ──X──► child          (no parent history leaks in)
child transcript  ──X──► parent         (only the summary comes back)
workspace         ─────► shared         (edits persist)
```

The `X`s are the feature. The child cannot ask clarifying questions, cannot see
what the parent already ruled out, and does not know the user's tone. So the
task statement must be **self-contained**:

```
Bad : "Fix the thing we discussed."
Good: "In repo /work/app, find why `test_checkout` fails. Report the root
       cause and the file:line, do not edit anything."
```

The last clause matters: without it, a read-only investigation will start
editing.

## The telephone game

A subagent returns prose. Prose loses detail. The parent then acts on the lossy
version.

```
child:  "the bug is in the retry logic in client.py:88"
parent: "fix the retry logic in client.py"
→ parent edits the wrong retry (there are three)
```

Mitigations:

- Require **structured output**: `file:line`, exact identifiers, test names.
- Require the child to **quote** the evidence, not paraphrase it.
- Make the summary **verifiable**: the parent re-reads the cited location.
- Prefer children that return *diffs or patches* over descriptions, when they
  are allowed to write.

## Parallelism and races

```python
results = run_parallel(parent, {
    "security": "audit src/ for injection",
    "tests":    "run the suite, report failures",
})
```

This is safe only because both jobs are read-only. If two agents write to the
same file:

```
agent A reads app.py (v1)
agent B reads app.py (v1)
A writes v2
B writes v3, based on v1  → A's change is gone
```

Options, best first:

1. **Don't parallelise writes.** Serialise, or partition by file ownership.
2. **Worktrees.** One checkout per agent, merge afterwards. Conflicts become
   visible merges instead of silent overwrites.
3. **File locks.** Cheap, but agents retry and stall; only for coarse
   partitioning.

The `run_parallel` helper in `mini_agent/subagents.py` says this out loud: it is
honest about being unsafe for writes.

## The review pattern

The highest-value orchestration pattern in practice:

```
implementer (writes the change)
        │
        ▼  diff
reviewer (fresh context, no knowledge of intent)
        │
        ▼  findings: file:line + severity + suggestion
implementer (addresses findings)
```

The reviewer's value comes from **not knowing why** the change was made. It
reads the diff cold, like a colleague would. A reviewer that shares the
implementer's context inherits its blind spots.

Two rules:

- The reviewer must be **read-only**. A reviewer that can edit will "helpfully"
  rewrite things.
- The reviewer must **cite lines**. "This could be cleaner" is noise.

## Cost model

| Run | Turns | Context/turn | Relative cost |
|---|---|---|---|
| Inline exploration | 20 | growing to 30k | 1.0× |
| Subagent exploration | 25 (child) | capped at 15k | ~0.6× parent + child |
| Parallel read-only ×3 | 15 each | 10k each | ~1.5×, 3× faster |

Subagents are not free. They are a way to trade **money and latency** for
**context headroom and parallelism**. Measure before adopting.

## Failure modes

| Failure | Cause | Fix |
|---|---|---|
| Child does the wrong task | Ambiguous task statement | Self-contained prompt with scope |
| Parent misapplies the summary | Lossy prose | Structured output + verify citation |
| Duplicated work | Parent also investigated | Explicit division of labour |
| Silent overwrite | Parallel writes | Serialise or worktrees |
| Runaway fan-out | Child spawns children | Depth limit, turn budget per child |
| Cost blow-up | Many children, long runs | Cap count and turns; log token spend |

## Lab

```bash
python3 labs/L09_subagents.py
```

You will run a parent that delegates two read-only investigations, inspect the
child transcripts (system + user only), and confirm the parent's context stays
small. Then you will reproduce a write race and fix it with serialisation.

🔬 **Break it:** have two children write the same file and diff the result.

## ✅ Checkpoint

1. What does a subagent trade away, and what does it buy?
2. Why must a delegation prompt be self-contained?
3. Why is the review pattern stronger with a fresh context?
4. When is parallel writing safe?
5. What is the telephone-game failure and how do you mitigate it?

<details>
<summary>Answers</summary>

1. Trades fidelity/evidence and money for context headroom and parallelism.
2. The child sees no parent history and cannot ask questions.
3. It does not inherit the implementer's assumptions and blind spots.
4. Only with disjoint files or separate worktrees; otherwise serialise.
5. Summaries lose detail and the parent acts on the loss; require structured,
   cited, verifiable output.
</details>
