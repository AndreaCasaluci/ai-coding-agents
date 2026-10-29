# 15 — Capstone: Build and Defend an Agent

> **Objectives**
> - Build a small but real agent that uses every concept in the course.
> - Prove it with evals, not prose.
> - Write a retro that names what you would change.

## The brief

Build **`repo_doctor`**: an agent that audits a repository and produces an
actionable health report.

It must:

1. **Use tools** to inspect a repo (files, search, tests).
2. **Load a skill** that defines the audit procedure.
3. **Enforce a rule with a hook** that a prompt could not guarantee.
4. **Delegate** at least one investigation to a subagent.
5. **Pass an eval suite** of at least five cases, including one where it must
   *not* act.
6. **Run headless**, with a turn and token budget, producing a report file.

This is deliberately small. The point is coverage of the concepts, not scale.

## Why this project

A repo audit is:

- **read-mostly**, so the blast radius is small,
- **verifiable**, because the report can be checked against the repo,
- **multi-step**, so it exercises context and delegation,
- **real**, in the sense that you would actually use the output.

## Milestones

### M1 — Brief and constraints (30 min)

Write `capstone/BRIEF.md`:

```markdown
## Goal
Audit a repo and write REPORT.md with: risky patterns, missing tests,
stale dependencies, and a top-3 fix list.

## Non-goals
No code changes. No network. No dependency installation.

## Constraints
Read-only workspace. Max 12 turns. Report under 100 lines.
```

Non-goals are the most important section. They are what stops the agent from
"helpfully" fixing things.

### M2 — Evals before the agent (1 h)

Write five cases in `capstone/evals.py` **before** the implementation:

| Case | Setup | Expected |
|---|---|---|
| `finds_missing_tests` | module with no test file | report names it |
| `finds_todo_cluster` | three `TODO` in one file | report groups them |
| `respects_read_only` | any repo | zero file modifications |
| `no_false_alarm` | clean repo | report says "no major issues" |
| `reports_structure` | nested repo | report has required sections |

Grading is on the report content and the workspace state, never on the
transcript.

### M3 — Tool surface (1 h)

Start from `make_fs_tools`. Add only what the audit needs:

- `list_files`, `read_file`, `search` (already there),
- `run_tests` (allowlisted command, capped output),
- `write_report` (the only write, to one path).

Note what you did **not** add: `delete_file`, `run_shell`. The audit does not
need them, so they are attack surface for free.

### M4 — Skill (45 min)

`capstone/skills/repo-audit/SKILL.md`:

```markdown
---
name: repo-audit
description: Audit a repository for missing tests, TODO clusters, risky
  patterns, and stale config. Use when asked to review repo health.
---

1. List the top-level structure. Identify language and test layout.
2. Find test files. Compare against source modules. List untested modules.
3. Search for TODO/FIXME/HACK. Group by file.
4. Check for risky patterns: eval, exec, shell=True, hardcoded secrets.
5. Write REPORT.md with: Summary, Untested modules, TODO clusters,
   Risky patterns, Top 3 fixes.
Do not modify any file except REPORT.md.
```

The last line is a rule, not a guarantee — which is why M5 exists.

### M5 — Hook (45 min)

Enforce what the skill only asks for:

```python
hooks.on(PRE_EDIT, deny_paths(("src", "tests", ".git", ".env")))
```

Only `REPORT.md` is writable. A prompt says "don't modify"; a hook makes it
impossible.

Bonus: a `post_tool` hook that redacts anything matching a secret pattern, and
a `pre_tool` audit log.

### M6 — Subagent (45 min)

Delegate the security scan:

```python
security = run_subagent(parent, "security",
    "Scan this repo for eval/exec/shell=True/hardcoded secrets. "
    "Report file:line for each finding. Do not edit anything.")
```

The parent gets a summary, not 30k tokens of grep output. Verify the citations
by reading one of them.

### M7 — Run and pass evals (1 h)

```bash
python3 -m capstone.repo_doctor --eval
```

Iterate on the **skill and the prompt**, not on the grader. If you find
yourself weakening a check to pass, stop: the check is telling you something.

### M8 — Retro (30 min)

`capstone/RETRO.md`:

- What did the agent get wrong that surprised you?
- Which control caught it: test, hook, budget, or review?
- What would you change about the task statement?
- What did the subagent buy you, in tokens?
- What is still unproven?

## Rubric

| Criterion | Weight | Evidence |
|---|---|---|
| Tool surface is minimal and justified | 15% | code + BRIEF non-goals |
| Skill actually changes behaviour | 15% | transcript shows `load_skill` |
| Hook enforces a rule | 20% | a denied edit in the transcript |
| Subagent used appropriately | 15% | child transcript + summary |
| Evals are outcome-based and pass | 20% | `--eval` output |
| Retro is honest and specific | 15% | RETRO.md |

A project that passes evals but has a 12-tool surface with `run_shell` scores
lower than one with four tools and a clear brief.

## Stretch goals

- Add a **reviewer subagent** with a fresh context that critiques the report.
- Add **pass@3** reporting for the flakiest case.
- Add a **budget-exhaustion** case: a repo so large the agent must compact, and
  the report must still be coherent.
- Run it in CI on a schedule against a real repo and diff the reports.

## Defense questions

You should be able to answer these without notes:

1. Why is `run_shell` absent, and what would you need to add before including
   it?
2. Which eval would catch a regression where the agent starts editing `src/`?
3. What does the subagent cost, and what did it save?
4. Where could a prompt injection enter this system, and what bounds the damage?
5. If the report is wrong, how would you find out?

If you cannot answer 4 and 5, re-read modules 11 and 12.
