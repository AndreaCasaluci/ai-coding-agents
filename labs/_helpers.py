"""Shared helpers for the lab scripts."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Make `import mini_agent` work when running `python3 labs/L00_*.py`.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def note(text: str) -> None:
    print(f"  · {text}")


def temp_ws(prefix: str = "lab-"):
    """A disposable workspace under the OS temp dir."""
    return tempfile.TemporaryDirectory(prefix=f"mini-agent-{prefix}")


def tree(root: Path) -> str:
    lines = []
    for path in sorted(root.rglob("*")):
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(root)
        lines.append(f"{rel}{'/' if path.is_dir() else ''}")
    return "\n".join(lines) or "(empty)"
