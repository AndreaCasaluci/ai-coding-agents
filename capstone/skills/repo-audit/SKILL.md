---
name: repo-audit
description: Audit a repository for missing tests, TODO clusters, and risky patterns, then write REPORT.md. Use when asked to review repo health, audit a codebase, or find technical debt.
---

# Repository audit

## Procedure

1. Load the file inventory: source files under `src/`, tests under `tests/`.
2. Find TODO/FIXME/HACK markers with `search`. Group them by file.
3. Search for risky patterns: `eval(`, `exec(`, `shell=True`, hardcoded
   credentials.
4. Delegate the security scan to a subagent. Ask for `file:line` citations and
   tell it not to edit anything.
5. Write `REPORT.md` with exactly these sections:

   ```
   # Repo audit

   ## Summary
   ## Untested modules
   ## TODO clusters
   ## Risky patterns
   ## Top 3 fixes
   ```

6. If there is nothing to report, say "No major issues found." in Summary and
   "None." in each list section.

## Rules

- Write only `REPORT.md`. Never modify source, tests, or config.
- Cite `file:line` for every finding. A finding without a location is a rumour.
- Keep the report under 100 lines.
- Do not invent files. If the inventory does not list it, it does not exist.
