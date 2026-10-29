# AGENTS.md

Instructions for coding agents working in this repository.

## Commands

- Test: `python3 run.py test`
- All labs: `python3 run.py labs`
- Lint (compile check): `python3 run.py lint`
- Run the agent: `python3 -m mini_agent "<task>" --root .`

No third-party dependencies. Python 3.10+.

## Invariants

- `mini_agent/` is teaching code: prefer clarity over cleverness, and keep
  modules small enough to read in one sitting.
- Every lab (`labs/L*.py`) must run standalone and exit 0.
- Every module in `lessons/` maps to a lab and a `mini_agent` module.
- Do not add a dependency. The stdlib-only constraint is part of the design.
- Tests live in `tests/` and use `unittest`, not pytest.

## Traps

- `make` is not installed in every environment. Use `python3 run.py ...` in
  docs and CI.
- Labs write to the OS temp directory, never into the repo.
- `.gitignore` excludes `sandbox/` and `.mini_agent/`; do not commit them.

## Style

- British spelling in prose ("summarise", "behaviour"), consistent with the
  lessons.
- ASCII diagrams, no Unicode box drawing.
- Code comments explain *why*, not *what*.
