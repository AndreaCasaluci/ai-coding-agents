# 14 — Teams, CI, Measurement

> **Objectives**
> - Run agents headlessly in CI without giving them the keys to production.
> - Calibrate trust instead of assuming it.
> - Choose metrics that survive a CFO review.

## Two modes of use

| Mode | Human present | Typical use |
|---|---|---|
| **Interactive** | yes | exploration, refactors, debugging |
| **Headless** | no | CI checks, issue triage, scheduled maintenance |

Headless is where the interesting engineering is, because nobody is there to
say "wait, don't do that". Every guard from module 12 must be mechanical.

## Headless agents in CI

```
pull_request
   │
   ├─ lint / typecheck / test          (deterministic, fast)
   ├─ agent: review diff               (read-only, posts comments)
   ├─ agent: fix lint failures         (write, on a branch, no push to main)
   └─ human review                     (final authority)
```

Rules that keep this sane:

1. **Read-only by default.** A reviewer agent gets no write token.
2. **Writes go to a branch**, never to the base branch.
3. **No secrets in the environment** unless the task genuinely needs them, and
   then scoped and short-lived.
4. **Pin the model and prompt version.** Otherwise yesterday's green build
   means nothing.
5. **Budget caps.** A per-run token/dollar limit, enforced by the harness.
6. **Timeouts.** Both per turn and per job.
7. **Deterministic fallback.** If the agent fails, the pipeline should still
   produce a useful result (e.g. "review unavailable").

### What to automate first

In order of value:

1. **Review comments on diffs** — read-only, low risk, immediate value.
2. **Issue triage / labelling** — low risk, high volume.
3. **Fixing lint and type errors** — narrow, verifiable.
4. **Dependency updates** — mechanical, test-gated.
5. **Feature work** — last, and only with a human in the loop.

Do not start with 5.

## Trust calibration

Trust is not binary. It is a per-task property:

```
task risk = blast radius × reversibility × verifiability
```

| Task | Blast radius | Reversible | Verifiable | Trust |
|---|---|---|---|---|
| Rename a variable | small | yes | yes | high |
| Add a test | small | yes | yes | high |
| Fix a bug | medium | yes | yes | medium |
| Refactor a module | medium | yes | medium | medium |
| Change a DB schema | large | no | hard | low |
| Touch auth / payments | large | no | hard | very low |
| Deploy | huge | no | no | none |

The mistake teams make is applying a single trust level to all of it.

## Metrics

Measure outcomes, not activity:

| Metric | Definition | Why it matters |
|---|---|---|
| **Acceptance rate** | % of agent diffs merged unchanged | signal vs noise |
| **Revert rate** | % reverted within 30 days | real correctness |
| **Human edit rate** | lines changed by humans after agent | quality gap |
| **Cycle time** | issue → merged PR | the actual goal |
| **Cost per merged PR** | tokens + infra / merged PRs | unit economics |
| **Escaped defects** | bugs traced to agent changes | risk |

Avoid:

- lines of code generated (rewards verbosity),
- number of agent sessions (rewards usage),
- "time saved" self-reported without a baseline.

### A cheap baseline experiment

Before rolling out, measure one week without agents: PR cycle time, review
comments per PR, revert rate. Then measure again. Without a baseline, every
number is a story.

## Review burden

The hidden cost is not tokens; it is **review attention**.

A 400-line agent diff takes ~30–60 minutes to review properly. If the agent
produces five a day, you have created a full-time review job. This is why
**small diffs and narrow scope are not style preferences — they are the
economics of the whole practice.**

Mitigations:

- cap diff size in the agent's instructions and enforce it with a hook,
- require tests in the same PR,
- route trivial changes to a faster review path,
- make the agent explain *why*, so the reviewer can skim the *what*.

## Policy: what agents may touch

Write it down, because "use judgement" produces inconsistent risk:

```markdown
## Agent policy

Allowed without review: docs, tests, lint fixes, dependency patches.
Allowed with review:    application code, CI config.
Approval required:      migrations, auth, payments, infra, secrets.
Never:                  force-push, deploy, rotate credentials, delete data.
```

Put the policy in `AGENTS.md` *and* enforce the important parts in hooks and
permissions. Policy documents drift; hooks do not.

## Onboarding a team

1. **Shared `AGENTS.md`** — commands, invariants, traps. One file, versioned.
2. **Shared skills** — the procedures the team repeats (release notes,
   migrations, incident runbooks).
3. **Shared hooks** — protect secrets, format on edit, audit calls.
4. **A starter eval suite** — five cases that encode "what good looks like".
5. **A review checklist** — so humans review the same things every time.
6. **A cost dashboard** — so the spend is visible before someone asks.

The order matters: context first, then capability, then guardrails, then
measurement.

## Governance, briefly

Questions that come up once agents touch real systems:

- **Who is accountable for an agent's commit?** The human who merged it.
- **Are agent commits labelled?** They should be, for auditability.
- **Is the transcript retained?** If yes, where, and for how long? It may
  contain code and secrets.
- **Can a model provider train on it?** Check the contract, not the marketing.
- **What is the rollback plan?** Same as for humans: revert, feature flag,
  redeploy.

## Lab

```bash
python3 labs/L14_ci.py
```

You will run the harness in a simulated CI job: read-only review mode, a token
budget, a turn limit, and a machine-readable report. Then you will flip it to
write mode and watch the permission layer refuse to push to `main`.

🔬 **Break it:** remove the budget cap and run a policy that loops; watch the
job hit the wall-clock timeout instead of failing cleanly.

## ✅ Checkpoint

1. What are the two modes of agent use, and which needs stronger guardrails?
2. Why should a CI reviewer be read-only?
3. What makes a task high-risk, in the trust formula?
4. Why is "lines of code" a bad metric?
5. Why is review burden the real cost of agent adoption?

<details>
<summary>Answers</summary>

1. Interactive and headless; headless needs mechanical guardrails because no
   human is watching.
2. It cannot accidentally fix things, and a compromised review cannot change
   the code it reviews.
3. Large blast radius, irreversible, hard to verify.
4. It rewards verbosity and measures activity, not outcomes.
5. Every agent diff consumes human review attention, which is the scarcest
   resource in the loop.
</details>
