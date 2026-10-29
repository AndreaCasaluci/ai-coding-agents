"""Tool wrappers for skills, so disclosure is a model decision."""

from __future__ import annotations

from .skills import SkillLibrary


def make_skill_tools(library: SkillLibrary) -> list:
    from .tools import tool

    @tool(name="load_skill")
    def load_skill(name: str) -> str:
        """Load the full instructions for a skill. Call this when the task matches a skill description."""
        return library.load(name)

    @tool(name="read_skill_resource")
    def read_skill_resource(skill: str, path: str) -> str:
        """Read a resource file bundled with a skill (e.g. a template or script)."""
        found = library.skills.get(skill)
        if found is None:
            raise ValueError(f"Unknown skill `{skill}`. Available: {', '.join(library.skills)}")
        return found.read_resource(path)

    return [load_skill, read_skill_resource]
