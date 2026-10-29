# 11 — Verification & Evals

> **Objectives**
> - Build a verification ladder and know which rung you are on.
> - Design an eval that measures outcomes, not vibes.
> - Report pass@k honestly.

## The core asymmetry

A model's claim of success is **text**. A test result is **evidence**. Agents
are fluent at the first and only occasionally produce the second on their own.

So the harness's most valuable job is not generating code. It is **creating
cheap, unambiguous signals of failure** that the loop can act on.

```
model says "done"  ──►  is that true?
                          │
                          ├─ no signal     → you are trusting prose
                          └─ test result   → you are engineering
```

## The verification ladder

Cheapest and most reliable first:

| Rung | Signal | Catches | Misses |
|---|---|---|---|
| 1 | parses / compiles | syntax errors | everything else |
| 2 | linter | style, obvious bugs | logic |
| 3 | type checker | interface mismatches | runtime behaviour |
| 4 | unit tests | specified behaviour | integration, spec gaps |
| 5 | integration / e2e | wiring, real I/O | performance, UX |
| 6 | manual review of the diff | intent, design | scale |

An agent with rungs 1–4 in its tool loop will self-correct most mistakes. An
agent with none will confidently ship broken code.

**The highest-leverage thing you can do for agent quality is make the test
suite fast and runnable by the agent.** Not a better model. A 2-second test
suite changes behaviour; a 10-minute one gets skipped.

## Self-review is weak; external review is not

"Review your own change" mostly produces reassurance. The model has already
committed to a plan and will rationalise it.

What works:

- **Run something** that can contradict it (tests, typechecker, a second
  opinion model with a fresh context — module 09).
- **Ask for a diff review with a rubric**: correctness, edge cases, security,
  test coverage, scope creep. Specific categories produce specific findings.
- **Require evidence in the answer**: "paste the command and its output".

## Eval anatomy

An eval is three things:

```python
EvalCase(
    name="fix empty-date crash",
    task="parse_date('') crashes. Fix it without changing the signature.",
    setup=lambda ws: seed_repo(ws),
    check=lambda result, ws: run_tests(ws) or "tests still failing",
)
```

1. **Task** — a self-contained instruction.
2. **Environment** — a *fresh* workspace, seeded identically every time.
3. **Grader** — a function over the outcome (files, test results), not the
   transcript.

That last point is the most common mistake. Grading `"did it call edit_file?"`
rewards mimicry. Grading `"do the tests pass?"` rewards the result.

## Rules that make evals trustworthy

| Rule | Why |
|---|---|
| Fresh state per case | Otherwise you test execution order |
| Grade outcomes | Transcripts are brittle and gameable |
| Include a case the agent should **refuse** | Catches over-eagerness |
| Include a **no-op** case | Catches unnecessary changes |
| Pin the model and settings | Otherwise the number is meaningless |
| Run k times | Non-determinism means one run is noise |
| Keep a held-out set | Otherwise you overfit prompts to the eval |

## pass@k, and why one green run lies

If an agent succeeds 70% of the time, a single run is a coin flip that lands
heads most days. Report:

```
pass@1 = 0.70     pass@3 = 0.97     pass@5 = 0.998
```

For coding agents, the number that matters is usually **pass@1 with retries
disabled** — that is what your CI will experience. pass@k with k retries is
what a human in the loop experiences.

## Flaky evals

An eval that passes and fails without code changes is worse than no eval: it
teaches you to ignore failures.

Common causes:

- shared temp directories or ports,
- time/date dependence,
- network calls,
- ordering assumptions,
- non-deterministic model temperature,
- a grader that depends on the transcript.

Quarantine flaky cases, then fix the environment. Never "just retry" in CI
without recording it.

## Regression suites

The eval suite grows from incidents:

```
bug found in production
  → write an eval that reproduces it
  → fix the agent/prompt/tool
  → the eval stays forever
```

This is exactly how test suites grow, and it works for the same reason: it
turns a one-off failure into a permanent guard.

## Metrics that are not vanity

| Metric | What it tells you |
|---|---|
| pass@1 on a fixed suite | capability |
| turns per success | efficiency |
| tokens per success | cost |
| human edits after the agent | quality gap |
| revert rate | real-world correctness |
| time to first useful diff | latency |
| % sessions abandoned | usability |

"Lines of code generated" is not on the list. It measures the wrong thing.

## Lab

```bash
python3 labs/L11_evals.py
```

You will build a three-case eval suite (a fix, a no-op, a refusal), run it
against two scripted models, and see one pass and one fail — then compute
pass@k on a flaky policy.

🔬 **Break it:** grade on `result.tool_calls` instead of the workspace and watch
a wrong-but-plausible agent pass.

## ✅ Checkpoint

1. Why is a model's "done" not evidence?
2. Name the verification ladder from cheapest to strongest.
3. Why must evals grade outcomes, not transcripts?
4. Why is one green run not a result?
5. What makes an eval flaky, and why is that worse than no eval?

<details>
<summary>Answers</summary>

1. It is unverified text; only environment observations are evidence.
2. Compile → lint → types → unit → integration → manual review.
3. Transcripts are brittle and reward mimicry; outcomes measure the result.
4. Non-determinism: you need k runs and a pass@k number.
5. Shared state, time, network, ordering; it trains you to ignore failures.
</details>
