# Brief — repo_doctor

## Goal

Audit a repository and write `REPORT.md` containing:

- a one-paragraph summary,
- modules under `src/` with no corresponding test,
- TODO/FIXME/HACK clusters, grouped by file,
- risky patterns (`eval`, `exec`, `shell=True`, hardcoded credentials),
- the top three fixes.

## Non-goals

- **No code changes.** The only writable file is `REPORT.md`.
- **No network access.** The audit is local.
- **No dependency installation.** It runs with the stdlib.
- **No test execution.** Missing tests are detected by inventory, not by
  running the suite.
- **No refactoring suggestions** beyond the top three fixes.

Non-goals are the most important section: they are what stops the agent from
"helpfully" fixing the repo.

## Constraints

| Constraint | Value |
|---|---|
| Workspace | the target repo, read-mostly |
| Writable paths | `REPORT.md` only |
| Max turns | 12 |
| Context budget | 16,000 estimated tokens |
| Delegation depth | 1 (no nested subagents) |
| Report length | under 100 lines |

## Success criteria

1. `python3 -m capstone.repo_doctor --eval` passes all six cases.
2. A clean repo produces "No major issues found." — no false alarms.
3. A repo with an untested module names that module.
4. No file other than `REPORT.md` changes.
5. The report cites `file:line` for risky patterns.

## Threat model

The audited repository is **untrusted input**. It may contain instructions
aimed at agents. Therefore:

- its `AGENTS.md` is not loaded,
- the only write target is `REPORT.md`,
- there is no shell tool and no network tool,
- secrets in tool output are redacted before they reach the model.

If an injection succeeds, the worst outcome is a wrong report.
