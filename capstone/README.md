# Capstone — repo_doctor

An audit agent that reads a repository and writes `REPORT.md`. It is the
smallest project that exercises every concept in the course at once.

## Run it

```bash
# audit a generated sample repo (offline, no API key)
python3 -m capstone.repo_doctor --demo

# audit a real repo
python3 -m capstone.repo_doctor --root /path/to/repo --transcript

# run the eval suite
python3 -m capstone.repo_doctor --eval
```

## What it demonstrates

| Concept | Where |
|---|---|
| Minimal tool surface | `build_doctor`: read, search, inventory, write, delegate |
| Skill loaded on demand | `capstone/skills/repo-audit/SKILL.md` via `load_skill` |
| Deterministic guard | `report-only` hook on `PRE_EDIT` |
| Secret redaction | `redact_secrets` on `POST_TOOL` |
| Subagent | `delegate` → `run_subagent`, fresh context, depth limit |
| Budget + turn cap | `ContextBudget(16_000)`, `max_turns=12` |
| Outcome evals | `capstone/evals.py`, six cases, fresh workspace each |
| Untrusted input | the audited repo's `AGENTS.md` is deliberately **not** loaded |

## Design decisions worth defending

**Only `REPORT.md` is writable.** The skill says so, but the hook enforces it.
Try `--root` on a repo and watch a write to `src/` come back as `DENIED`.

**No shell tool.** The audit does not need one, so it is absent. Every tool you
do not expose is an attack surface you do not own.

**The audited repo's instructions are ignored.** A repository can contain an
`AGENTS.md` that says "exfiltrate the secrets". Loading it would be a
self-inflicted injection. The doctor starts with an empty `InstructionSet`.

**Delegation is one level deep.** The `delegate` tool refuses when the calling
agent is not the root doctor, so a child cannot fan out indefinitely.

**The offline model is a state machine.** `DoctorLLM` performs the procedure
deterministically so the capstone runs with no API key. Swap in a real model
with `MINI_AGENT_PROVIDER=openai`; the harness is identical.

## Extend it

- Add a **reviewer subagent** that critiques the report with a rubric.
- Add **pass@3** for the flakiest case.
- Add a **budget-exhaustion** case: a repo large enough to force compaction.
- Run it on a schedule in CI and diff the reports.

## Files

```
capstone/
  repo_doctor.py        the agent, tools, hook, policy, CLI
  evals.py              six outcome-graded cases
  skills/repo-audit/    the procedure (SKILL.md)
  BRIEF.md              the task statement and non-goals
  RETRO.md              what you learned (fill this in)
```
