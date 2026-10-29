"""Lab 07 — Skills and progressive disclosure.

Run: python3 labs/L07_skills.py

Goal: measure the cost of N skills at each disclosure level, and see how the
description decides whether a skill loads.
"""

from __future__ import annotations

from pathlib import Path

from _helpers import note, section, temp_ws

from mini_agent.context import estimate_tokens
from mini_agent.skills import SkillLibrary

SKILLS = {
    "release-notes": (
        "Write release notes from git history. Use when asked to prepare a "
        "release, changelog, or 'what changed since vX'.",
        """\
# Release notes

1. Get the range: `git log --oneline <last-tag>..HEAD`.
2. Group: features, fixes, breaking changes, chores.
3. Drop merge commits and version bumps.
4. Follow `template.md`. Bullets under 100 chars.
5. If breaking, put it first and mark it **BREAKING**.
""",
    ),
    "db-migration": (
        "Create and review a database migration. Use when a schema change is "
        "needed, or when asked about alembic revisions.",
        """\
# Database migration

1. Generate: `python3 skills/db-migration/new_migration.py <name>`.
2. Never hand-write the revision id; the timestamp format matters.
3. Add a downgrade path. If irreversible, say so in the docstring.
4. Run `make test` — the suite resets the DB per test.
""",
    ),
    "incident-runbook": (
        "Triage a production incident: assess blast radius, mitigate, then "
        "write a timeline. Use when paged or asked about an outage.",
        """\
# Incident runbook

1. Declare severity and open an incident channel.
2. Mitigate first (rollback, feature flag), diagnose second.
3. Record timestamps as you go; the timeline is the deliverable.
4. Post-incident: blameless review within 48h.
""",
    ),
}


def build(root: Path) -> None:
    for name, (description, body) in SKILLS.items():
        folder = root / "skills" / name
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {description}\n---\n\n{body}")
    (root / "skills" / "release-notes" / "template.md").write_text("# vX.Y.Z\n\n## Features\n- \n")


def main() -> None:
    with temp_ws("skills") as tmp:
        root = Path(tmp)
        build(root)
        library = SkillLibrary.discover(root / "skills")

        section("1. THE CATALOG (L1)")
        catalog = library.catalog()
        print(catalog)
        print(f"\n  {len(library)} skills, catalog = {estimate_tokens(catalog)} tokens")
        note("This is what sits in the system prompt, always, for every skill you own.")

        section("2. THE COST OF LOADING EVERYTHING (L2)")
        everything = "\n\n".join(library.load(name) for name in library.skills)
        print(f"  all bodies      = {estimate_tokens(everything):>5} tokens")
        print(f"  catalog only    = {estimate_tokens(catalog):>5} tokens")
        print(f"  ratio           = {estimate_tokens(everything) / estimate_tokens(catalog):.0f}x")
        note("At 10–20 skills, loading all bodies would consume the whole budget.")

        section("3. LOAD ONE (L2)")
        print(library.load("db-migration")[:400])

        section("4. READ A RESOURCE (L3)")
        print(library.skills["release-notes"].read_resource("template.md"))

        section("5. THE DESCRIPTION IS THE TRIGGER")
        tasks = [
            "prepare the changelog for v2.1",
            "we need a new column on users",
            "site is down, paged at 03:12",
            "refactor the checkout module",
        ]
        for task in tasks:
            matches = library.match(task)
            chosen = matches[0].name if matches else "(none)"
            print(f"  {task!r:<42} -> {chosen}")

        section("6. WHEN DESCRIPTIONS GO WRONG")
        from mini_agent.skills import Skill

        bad = SkillLibrary([
            Skill(name="helper", description="Helps with things", body="…", path=root)
        ])
        for task in tasks:
            matches = bad.match(task)
            print(f"  {task!r:<42} -> {matches[0].name if matches else '(never loads)'}")
        note("A vague description is a skill that never loads. Dead weight.")

        section("7. SKILL VS TOOL VS INSTRUCTION")
        note("instruction: a constraint, always loaded  ('run make test')")
        note("skill      : a procedure, loaded on demand ('how to write a migration')")
        note("tool       : an action, schema always, result on call ('read_file')")


if __name__ == "__main__":
    main()
