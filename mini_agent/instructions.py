"""Instruction files (AGENTS.md) and precedence.

Instruction files are the cheapest, highest-leverage steering mechanism in
coding agents. They are plain Markdown, versioned with the code, and read
automatically. The design questions are always the same:

* **Where does it live?** Root = project-wide. Subdirectory = scoped to that
  subtree. User-level = personal, not committed.
* **What wins when they conflict?** Proximity. The file closest to the work
  overrides the one above it.
* **What belongs in it?** Commands that are not guessable, invariants that are
  not obvious, and traps that cost real time. Not a style essay.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

INSTRUCTION_FILENAMES = ("AGENTS.md",)


@dataclass
class Instruction:
    path: Path
    text: str
    scope: str  # "root", "subdir", or "user"


@dataclass
class InstructionSet:
    items: list[Instruction] = field(default_factory=list)

    def render(self) -> str:
        """Concatenate in precedence order: broadest first, closest last."""
        if not self.items:
            return ""
        blocks = []
        for item in self.items:
            blocks.append(f"<!-- from {item.path} ({item.scope}) -->\n{item.text.strip()}")
        return "\n\n".join(blocks)

    def sources(self) -> list[str]:
        return [str(i.path) for i in self.items]


def discover(root: Path, start: Path | None = None, user_file: Path | None = None) -> InstructionSet:
    """Collect instruction files from the root down to ``start``.

    Root-level files come first, deeper files later, so the model reads
    "general → specific". This matches how humans read a hierarchy and gives
    proximity-based precedence for free.
    """
    root = Path(root).resolve()
    start = Path(start or root).resolve()
    if root not in start.parents and start != root:
        start = root

    items: list[Instruction] = []

    if user_file and Path(user_file).exists():
        items.append(Instruction(Path(user_file), Path(user_file).read_text(encoding="utf-8"), "user"))

    chain = [start, *start.parents]
    chain = [p for p in chain if root == p or root in p.parents]
    chain.reverse()  # root first

    for directory in chain:
        for filename in INSTRUCTION_FILENAMES:
            candidate = directory / filename
            if candidate.is_file():
                scope = "root" if directory == root else "subdir"
                items.append(Instruction(candidate, candidate.read_text(encoding="utf-8"), scope))

    return InstructionSet(items)


def merge(*sets: InstructionSet) -> InstructionSet:
    """Combine sets, de-duplicating by path, preserving order."""
    seen: set[str] = set()
    merged = InstructionSet()
    for s in sets:
        for item in s.items:
            key = str(item.path.resolve())
            if key in seen:
                continue
            seen.add(key)
            merged.items.append(item)
    return merged


def scaffold(path: Path, project_name: str = "this project") -> Path:
    """Write a starter AGENTS.md. Note how short it is on purpose."""
    path = Path(path)
    path.write_text(
        f"""# AGENTS.md — {project_name}

## Commands

- Test: `make test`
- Lint: `make lint`
- Run: `python3 -m app`

## Invariants

- Never commit to `main`; branch first.
- Do not edit generated files (`*_pb2.py`, `dist/`).
- Secrets live in `.env`; never read or print it.

## Traps

- The test suite needs a database; `make test` starts one.
- `legacy/` is frozen. Do not refactor it.
""",
        encoding="utf-8",
    )
    return path
