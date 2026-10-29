# 06 — Instructions & Rules Files

> **Objectives**
> - Write an `AGENTS.md` that changes behaviour.
> - Reason about precedence when instructions conflict.
> - Avoid the three anti-patterns that make instruction files useless.

## The problem

Every session starts cold. Without a persistent instruction file, you retype
the same context: how to run tests, which directories are frozen, what not to
touch. That is wasted tokens and inconsistent behaviour.

The convention that has emerged is `AGENTS.md`: plain Markdown at the repo root,
read automatically, versioned with the code.

## What actually belongs in it

Three categories, and nothing else:

### 1. Commands that are not guessable

```markdown
## Commands
- Test: `make test`          (starts a Postgres container)
- Single test: `pytest tests/test_x.py::test_y`
- Lint: `ruff check . && mypy src`
- Generate protos: `make proto`  (do not hand-edit *_pb2.py)
```

The model can guess `pytest`. It cannot guess that the suite needs a database,
or that generated files must not be edited.

### 2. Invariants that are not obvious

```markdown
## Invariants
- Never commit to `main`; branch first.
- Public API changes require a changelog entry in `CHANGELOG.md`.
- Money is integer cents. Never use floats for currency.
- All DB access goes through `db/repo.py`.
```

These are the rules that, when broken, cost a review cycle or a production
incident.

### 3. Traps that cost real time

```markdown
## Traps
- `legacy/` is frozen. Do not refactor it, even if it looks wrong.
- The test suite is order-dependent; run it whole, not file-by-file.
- `config/defaults.yaml` is generated from `config/schema.py`.
```

## What does not belong

| Anti-pattern | Why it fails |
|---|---|
| A style essay ("write clean code") | Too vague to change any decision |
| Duplicating the README | Stale the moment it changes; two sources of truth |
| A 500-line architecture doc | Eats the budget; buried rules get ignored |
| Every rule you can think of | Dilution: the important rule is now 1 of 80 |
| Aspirational rules nobody follows | Teaches the model that rules are optional |

A good `AGENTS.md` is **30–80 lines**. If it is longer, most of it belongs in
documentation that the agent can read on demand, or in a skill.

## Precedence

Real systems have layers:

```
user-level instructions      (~/.config/agent/AGENTS.md)   personal, not committed
        ▲ overridden by
repo-root AGENTS.md                                        project-wide
        ▲ overridden by
subdirectory AGENTS.md                                     scoped to a subtree
        ▲ overridden by
the current task / user message                            this session only
```

Two rules:

1. **Closer wins.** A `backend/AGENTS.md` overrides the root for work under
   `backend/`.
2. **Specific beats general.** "Use tabs here" beats "use spaces" if it is
   more local.

Ambiguity is the enemy. If two files disagree and neither is clearly more
local, the model will pick one at random and you will not know which.

## Negative instructions are weak

```
Don't use print statements.          ← model may still add one
Use the logger in `obs/log.py`.      ← actionable
```

A prohibition tells the model what not to do but not what to do instead. Pair
every "don't" with a "do", or it will fill the gap with a guess.

Weak: "Don't break the build."
Strong: "Before finishing, run `make check` and paste the result."

## Make it testable

An instruction you cannot verify is a wish. Prefer rules whose violation is
visible:

- "Run `make test` before declaring done" → check the transcript for the call.
- "Never edit `legacy/`" → a hook can enforce it (module 08).
- "Use integer cents" → a lint rule or a test can enforce it.

The progression is: **instruction → hook → test → type system**. Move a rule
down that ladder as soon as it matters.

## Scoping by directory

Large repos benefit from per-directory instructions:

```
AGENTS.md                      # repo-wide: commands, invariants
backend/AGENTS.md              # Django conventions, migration policy
frontend/AGENTS.md             # component patterns, state management rules
infra/AGENTS.md                # never apply terraform without a plan file
```

`discover()` in `mini_agent/instructions.py` walks from the workspace root down
to the working directory, so the model reads general → specific.

💡 *In practice* — Tools differ in filename and discovery rules (some read
`AGENTS.md`, some have their own, some support both). The concept is identical:
a versioned Markdown file, layered by directory, loaded into the system prompt.

## Lab

```bash
python3 labs/L06_instructions.py
```

You will build a small repo with root and subdirectory instruction files, watch
them render in precedence order, and see a vague instruction fail to change a
scripted model's behaviour while a specific one succeeds.

🔬 **Break it:** write two conflicting instructions at the same level and see
which one the model follows. Then fix it by making one more specific.

## ✅ Checkpoint

1. What three categories belong in `AGENTS.md`?
2. Why is "write clean code" a useless instruction?
3. What is the precedence rule between root and subdirectory files?
4. Why are negative instructions weak, and what is the fix?
5. What is the ladder from instruction to enforcement?

<details>
<summary>Answers</summary>

1. Non-guessable commands, non-obvious invariants, time-costing traps.
2. It does not change any concrete decision; it cannot be violated visibly.
3. The closer file wins for work in its subtree.
4. They say what not to do, not what to do; pair with a positive alternative.
5. Instruction → hook → test → type system.
</details>
