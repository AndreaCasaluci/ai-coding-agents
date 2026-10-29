# 13 — Workflows That Work

> **Objectives**
> - Structure a session so the agent succeeds and you can verify it.
> - Use TDD and plan-first as control mechanisms, not rituals.
> - Know when to stop the agent and take over.

## The session shape

```
1. EXPLORE   read, search, understand        (read-only)
2. PLAN      state the change, list files    (no edits)
3. EXECUTE   small edits, one concern        (writes)
4. VERIFY    tests, types, diff review       (evidence)
5. REPORT    what changed, what is unproven  (honest summary)
```

Most failed sessions skip 1–2 and rush to 3. The agent then edits the wrong
file, and every subsequent turn compounds the error.

### Explore and plan are cheap

Exploration is read-only, so it cannot break anything. Planning costs one turn
and catches "I misunderstood the task" before it becomes a 30-file diff.

```
"Before changing anything: find where auth tokens are validated, list the
 files involved, and propose a plan. Do not edit yet."
```

The `do not edit yet` clause is what makes it a plan. Without it, models start
writing during the explanation.

💡 *In practice* — Some tools have an explicit "plan mode" that mechanically
blocks writes. That is strictly better than asking nicely, because it is
enforced (module 08).

## TDD is an agent control system

Test-driven development is usually sold as a design practice. For agents it is
something more useful: **a specification the loop can check.**

```
1. Write the failing test (or ask for it, then review it).
2. Run it. Confirm it fails for the right reason.
3. Implement until it passes.
4. Run the whole suite.
5. Refactor with the suite green.
```

Why this works so well with agents:

- The test is a **fixed target**. The model cannot redefine success mid-run.
- Failure output is **evidence**, which re-enters the loop.
- The test survives the session and guards future changes.

The failure mode: the agent writes a test that asserts its own implementation.
Review the test first, or write it yourself. A test written after the code
tests that the code does what it does.

## Small diffs, one concern

| Diff size | Review reality |
|---|---|
| < 50 lines | read carefully |
| 50–300 | skim, trust the tests |
| 300–1000 | rubber stamp |
| > 1000 | "looks fine" |

Agents are happy to produce 2,000-line diffs. That is not productivity; it is
review debt. Constrain the task:

```
"Only change src/auth/session.py. Do not touch tests or config."
```

Scope is a prompt-level control; hooks and permissions are the enforcement
(module 12).

## Context hygiene

- **One task per session.** A session that drifts from "fix login" to "also
  upgrade React" has a contaminated context and an unreviewable diff.
- **Start fresh after a failure loop.** If the agent has failed three times,
  the transcript now contains three failed hypotheses, and they bias the next
  attempt. New session, better task statement.
- **Compact deliberately.** Summarise what you learned into the new task
  statement instead of dragging the whole history.
- **Keep the working tree clean** before starting, so `git diff` means
  something.

## When to take over

Stop the agent when:

- it has made the **same failed attempt twice** (it will make it a third time),
- the diff is **growing without tests passing**,
- it is **editing files outside the stated scope**,
- it is **arguing with the test** instead of fixing the code,
- you cannot explain the change it just made.

Taking over is not failure. The point is throughput, and a human fixing a
5-line bug is often faster than a fourth agent attempt.

## Commit hygiene

Agents make commits easy and therefore tempting to make badly.

- **One logical change per commit.**
- **The message explains why**, not just what (the diff shows what).
- **Never commit secrets**; check `git diff --cached` before committing.
- **Do not let the agent commit to `main`**; branch first, always.
- **Review before committing**, not after pushing.

A useful convention: the agent stages and proposes a message; the human
commits. It keeps the human in the loop at the point where mistakes become
permanent.

## The review checklist

When reviewing an agent diff, ask in this order:

1. **Scope** — does it touch only what was asked?
2. **Correctness** — is there a test, and does it test the right thing?
3. **Edge cases** — empty, null, large, concurrent, unauthorised.
4. **Error handling** — does it swallow failures?
5. **Security** — new inputs, new paths, new network calls?
6. **Style** — consistent with the surrounding code (least important).

The first two catch most real problems. Style is where reviewers spend most of
their time.

## Anti-patterns

| Anti-pattern | Symptom | Fix |
|---|---|---|
| Vibe-driven development | "looks right", no tests | require evidence |
| Prompt pile-up | 200-line task statement | plan first, split the task |
| Context hoarding | one session for a whole day | fresh session per task |
| Rubber-stamping | 1,000-line diff approved in 2 min | cap diff size |
| Agent commits everything | noisy history | human commits |
| Retry until green | flaky test hidden | fix the test |
| "It said it worked" | no verification | run it yourself |

## Lab

```bash
python3 labs/L13_workflows.py
```

You will run the same bug-fix task two ways: a one-shot "fix it" prompt, and the
explore → plan → test → fix → verify loop. Compare the transcripts, the diff
size, and the number of turns.

🔬 **Break it:** give the agent a task that spans three concerns and watch the
diff become unreviewable.

## ✅ Checkpoint

1. Why are explore and plan the cheapest phases?
2. Why does TDD work better with agents than with humans?
3. What is the failure mode of agent-written tests?
4. When should you stop the agent and take over?
5. Why review before committing rather than after pushing?

<details>
<summary>Answers</summary>

1. They are read-only, so they cannot break anything, and they catch
   misunderstanding before it becomes a large diff.
2. The test is a fixed target and its failure output is evidence the loop can
   act on.
3. The test asserts the implementation rather than the requirement.
4. Repeated identical failure, growing diff without green tests, scope creep,
   or a change you cannot explain.
5. Commits are cheap to fix before they exist and expensive after they are
   shared.
</details>
