"""A path-jailed filesystem workspace.

The filesystem is the agent's world, and it is also the main source of
catastrophic failure. Two rules encoded here:

1. **Resolve, then check.** Symlinks and ``..`` are how path checks get
   bypassed. Resolve to a real absolute path and verify containment *after*.
2. **Edits are unique-string replacements**, not whole-file rewrites. Rewrites
   silently destroy work when the model's copy of the file is stale.

This is a teaching implementation. It is not a security boundary against a
hostile process — see lesson 12 for what a real sandbox adds.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

MAX_READ_CHARS = 40_000
MAX_MATCHES = 200


class WorkspaceError(Exception):
    """Raised for every rejected operation. The agent sees the message."""


@dataclass
class Workspace:
    root: Path
    read_only: bool = False

    def __post_init__(self) -> None:
        self.root = Path(self.root).expanduser().resolve()
        if not self.root.exists():
            self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir():
            raise WorkspaceError(f"Workspace root is not a directory: {self.root}")

    # -- path handling -----------------------------------------------------
    def resolve(self, path: str) -> Path:
        """Map an agent-supplied path to a real path inside the jail."""
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        real = candidate.resolve()
        if real != self.root and self.root not in real.parents:
            raise WorkspaceError(
                f"Path escapes the workspace: {path!r} -> {real}. "
                "Use paths relative to the workspace root."
            )
        return real

    def rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)

    def _guard_write(self) -> None:
        if self.read_only:
            raise WorkspaceError("Workspace is read-only.")

    # -- reads -------------------------------------------------------------
    def list(self, path: str = ".", depth: int = 1) -> str:
        target = self.resolve(path)
        if not target.exists():
            raise WorkspaceError(f"No such path: {path}")
        if target.is_file():
            return self.rel(target)
        lines: list[str] = []
        self._walk(target, depth, lines)
        return "\n".join(lines) if lines else "(empty)"

    def _walk(self, directory: Path, depth: int, out: list[str], prefix: str = "") -> None:
        if depth < 0:
            return
        try:
            entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            out.append(f"{prefix}[permission denied]")
            return
        for entry in entries:
            if entry.name in {".git", "__pycache__", ".venv", "node_modules", ".mini_agent"}:
                continue
            marker = "/" if entry.is_dir() else ""
            out.append(f"{prefix}{entry.name}{marker}")
            if entry.is_dir() and depth > 0:
                self._walk(entry, depth - 1, out, prefix + "  ")

    def read(self, path: str, start: int = 1, end: int | None = None) -> str:
        target = self.resolve(path)
        if not target.exists():
            raise WorkspaceError(f"No such file: {path}")
        if target.is_dir():
            raise WorkspaceError(f"{path} is a directory; use list_files")
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise WorkspaceError(f"Could not read {path}: {exc}") from exc

        lines = text.splitlines()
        if start > 1 or end is not None:
            chunk = lines[start - 1 : end]
            numbered = [f"{i + start:>5}  {line}" for i, line in enumerate(chunk)]
            return "\n".join(numbered) or "(no lines in range)"
        if len(text) > MAX_READ_CHARS:
            cut = text[:MAX_READ_CHARS]
            return cut + f"\n\n[truncated: file is {len(text)} chars, showing {MAX_READ_CHARS}]"
        return text

    def search(self, pattern: str, path: str = ".", glob: str = "*", ignore_case: bool = False) -> str:
        target = self.resolve(path)
        try:
            rx = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
        except re.error as exc:
            raise WorkspaceError(f"Bad regex {pattern!r}: {exc}") from exc

        hits: list[str] = []
        files = [target] if target.is_file() else target.rglob(glob)
        for file in files:
            if not file.is_file() or _skip(file):
                continue
            try:
                for n, line in enumerate(file.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if rx.search(line):
                        hits.append(f"{self.rel(file)}:{n}: {line.strip()[:200]}")
                        if len(hits) >= MAX_MATCHES:
                            hits.append(f"[stopped at {MAX_MATCHES} matches]")
                            return "\n".join(hits)
            except OSError:
                continue
        return "\n".join(hits) if hits else "(no matches)"

    # -- writes ------------------------------------------------------------
    def write(self, path: str, content: str) -> str:
        self._guard_write()
        target = self.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} chars to {self.rel(target)}"

    def edit(self, path: str, old: str, new: str) -> str:
        """Replace exactly one occurrence. Ambiguity is an error, not a guess."""
        self._guard_write()
        target = self.resolve(path)
        if not target.exists():
            raise WorkspaceError(f"No such file: {path}")
        text = target.read_text(encoding="utf-8")
        count = text.count(old)
        if count == 0:
            raise WorkspaceError(f"`old` string not found in {path}. Read the file again.")
        if count > 1:
            raise WorkspaceError(
                f"`old` string appears {count} times in {path}. "
                "Include more surrounding context to make it unique."
            )
        target.write_text(text.replace(old, new, 1), encoding="utf-8")
        return f"Edited {self.rel(target)} (1 replacement)"

    def delete(self, path: str) -> str:
        self._guard_write()
        target = self.resolve(path)
        if not target.exists():
            raise WorkspaceError(f"No such file: {path}")
        if target == self.root:
            raise WorkspaceError("Refusing to delete the workspace root.")
        if target.is_dir():
            import shutil

            shutil.rmtree(target)
        else:
            target.unlink()
        return f"Deleted {self.rel(target)}"


def _skip(path: Path) -> bool:
    parts = set(path.parts)
    return bool(parts & {".git", "__pycache__", ".venv", "node_modules", ".mini_agent"})


# -- tools bound to a workspace -------------------------------------------
def make_fs_tools(ws: Workspace) -> list:
    """The canonical tool surface for a coding agent. Notice how small it is."""
    from .tools import tool

    @tool(name="list_files")
    def list_files(path: str = ".", depth: int = 2) -> str:
        """List files and directories under a path (relative to the workspace)."""
        return ws.list(path, depth)

    @tool(name="read_file")
    def read_file(path: str, start: int = 1, end: int | None = None) -> str:
        """Read a text file. Optionally read only lines [start, end]."""
        return ws.read(path, start, end)

    @tool(name="search")
    def search(pattern: str, path: str = ".", glob: str = "*", ignore_case: bool = False) -> str:
        """Search file contents with a regular expression. Returns path:line: text."""
        return ws.search(pattern, path, glob, ignore_case)

    @tool(name="write_file", side_effect=True, needs_permission=True)
    def write_file(path: str, content: str) -> str:
        """Create or overwrite a file. Overwriting destroys existing content."""
        return ws.write(path, content)

    @tool(name="edit_file", side_effect=True, needs_permission=True)
    def edit_file(path: str, old: str, new: str) -> str:
        """Replace exactly one unique occurrence of `old` with `new` in a file."""
        return ws.edit(path, old, new)

    @tool(name="delete_file", side_effect=True, needs_permission=True)
    def delete_file(path: str) -> str:
        """Delete a file or directory."""
        return ws.delete(path)

    return [list_files, read_file, search, write_file, edit_file, delete_file]
