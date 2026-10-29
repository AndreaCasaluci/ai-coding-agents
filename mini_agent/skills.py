"""Skills: discoverable procedures with progressive disclosure.

A skill is a folder:

    skills/
      release-notes/
        SKILL.md          # frontmatter + instructions
        template.md       # optional resource, loaded only if needed

Three levels of disclosure, and the whole design is about the ratio:

  L1  name + description      ~50 tokens per skill, always in context
  L2  full SKILL.md body      ~500-2000 tokens, loaded when the task matches
  L3  resources / scripts     unbounded, loaded or executed on demand

The failure mode to avoid: putting every procedure in the system prompt. Ten
skills at L2 is 20k tokens of mostly-irrelevant instructions, and models get
*worse* with more irrelevant context, not better.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


class SkillError(Exception):
    pass


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path
    resources: list[str] = field(default_factory=list)

    def catalog_line(self) -> str:
        return f"- {self.name}: {self.description}"

    def read_resource(self, rel: str) -> str:
        target = (self.path / rel).resolve()
        if self.path.resolve() not in target.parents and target != self.path.resolve():
            raise SkillError(f"Resource escapes skill folder: {rel}")
        if not target.is_file():
            raise SkillError(f"No such resource: {rel}")
        return target.read_text(encoding="utf-8", errors="replace")


_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


def parse_skill(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    if not match:
        raise SkillError(f"{path}: missing YAML frontmatter (--- name: ... ---)")
    meta = _parse_frontmatter(match.group(1))
    body = match.group(2).strip()

    name = meta.get("name") or path.parent.name
    description = meta.get("description", "").strip()
    if not description:
        raise SkillError(f"{path}: frontmatter needs a `description` — it is the trigger")
    if len(description) > 1024:
        raise SkillError(f"{path}: description is {len(description)} chars; keep it under 1024")

    resources = sorted(
        str(p.relative_to(path.parent))
        for p in path.parent.rglob("*")
        if p.is_file() and p.name != "SKILL.md"
    )
    return Skill(name=name, description=description, body=body, path=path.parent, resources=resources)


def _parse_frontmatter(block: str) -> dict[str, str]:
    """A deliberately tiny YAML subset: `key: value` and `key: >` folded text."""
    meta: dict[str, str] = {}
    key: str | None = None
    buffer: list[str] = []
    for raw in block.splitlines():
        if not raw.strip():
            continue
        if raw[:1] not in {" ", "\t"} and ":" in raw:
            if key is not None:
                meta[key] = " ".join(buffer).strip()
            key, _, value = raw.partition(":")
            key = key.strip()
            value = value.strip()
            buffer = [] if value in {">", "|", ""} else [value]
        elif key is not None:
            buffer.append(raw.strip())
    if key is not None:
        meta[key] = " ".join(buffer).strip()
    return meta


class SkillLibrary:
    """All skills found under a directory, with L1/L2/L3 accessors."""

    def __init__(self, skills: list[Skill] | None = None):
        self.skills: dict[str, Skill] = {s.name: s for s in skills or []}

    @classmethod
    def discover(cls, directory: Path) -> "SkillLibrary":
        directory = Path(directory)
        if not directory.is_dir():
            return cls()
        skills = []
        for skill_md in sorted(directory.glob("*/SKILL.md")):
            try:
                skills.append(parse_skill(skill_md))
            except SkillError as exc:
                # A broken skill should not take down the session. Warn, skip.
                print(f"[skills] skipping {skill_md}: {exc}")
        return cls(skills)

    def __len__(self) -> int:
        return len(self.skills)

    def catalog(self) -> str:
        """L1: what goes in the system prompt. Keep it to one line each."""
        if not self.skills:
            return ""
        return "\n".join(s.catalog_line() for s in self.skills.values())

    def load(self, name: str) -> str:
        """L2: the full procedure, injected when the task matches."""
        skill = self.skills.get(name)
        if skill is None:
            raise SkillError(f"Unknown skill `{name}`. Available: {', '.join(self.skills)}")
        extra = ""
        if skill.resources:
            extra = "\n\nResources you may read on demand:\n" + "\n".join(f"- {r}" for r in skill.resources)
        return f"# Skill: {skill.name}\n\n{skill.body}{extra}"

    def match(self, task: str) -> list[Skill]:
        """Cheap lexical trigger. Real systems use the model to choose."""
        words = {w for w in re.findall(r"[a-z]{4,}", task.lower())}
        scored = []
        for skill in self.skills.values():
            haystack = f"{skill.name} {skill.description}".lower()
            score = sum(1 for w in words if w in haystack)
            if score:
                scored.append((score, skill))
        return [s for _, s in sorted(scored, key=lambda pair: -pair[0])]
