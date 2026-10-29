import tempfile
import unittest
from pathlib import Path

from mini_agent.hooks import PRE_TOOL, HookBus, HookResult, deny_paths, redact_secrets
from mini_agent.instructions import discover
from mini_agent.skills import SkillError, SkillLibrary, parse_skill


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        skill_dir = self.root / "skills" / "release-notes"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: release-notes\ndescription: Write release notes from git history.\n---\n"
            "# Steps\n1. Read git log\n2. Group by type\n"
        )
        (skill_dir / "template.md").write_text("# vX.Y.Z\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_frontmatter(self):
        skill = parse_skill(self.root / "skills" / "release-notes" / "SKILL.md")
        self.assertEqual(skill.name, "release-notes")
        self.assertIn("release notes", skill.description)
        self.assertIn("Read git log", skill.body)
        self.assertIn("template.md", skill.resources)

    def test_missing_description_rejected(self):
        bad = self.root / "skills" / "bad"
        bad.mkdir()
        (bad / "SKILL.md").write_text("---\nname: bad\n---\nbody")
        with self.assertRaises(SkillError):
            parse_skill(bad / "SKILL.md")

    def test_catalog_is_one_line_per_skill(self):
        lib = SkillLibrary.discover(self.root / "skills")
        catalog = lib.catalog()
        self.assertEqual(len(catalog.splitlines()), 1)
        self.assertIn("release-notes", catalog)

    def test_load_and_resource(self):
        lib = SkillLibrary.discover(self.root / "skills")
        self.assertIn("Read git log", lib.load("release-notes"))
        self.assertIn("vX.Y.Z", lib.skills["release-notes"].read_resource("template.md"))

    def test_resource_escape_blocked(self):
        lib = SkillLibrary.discover(self.root / "skills")
        with self.assertRaises(SkillError):
            lib.skills["release-notes"].read_resource("../../../etc/passwd")

    def test_unknown_skill(self):
        lib = SkillLibrary.discover(self.root / "skills")
        with self.assertRaises(SkillError):
            lib.load("nope")

    def test_match_scores_by_words(self):
        lib = SkillLibrary.discover(self.root / "skills")
        self.assertEqual(lib.match("write release notes")[0].name, "release-notes")


class HookTests(unittest.TestCase):
    def test_deny_wins_and_stops_chain(self):
        bus = HookBus()
        calls = []
        bus.on(PRE_TOOL, lambda p: (calls.append("a"), None)[-1], name="a")
        bus.on(PRE_TOOL, lambda p: HookResult(False, "blocked"), name="b")
        bus.on(PRE_TOOL, lambda p: (calls.append("c"), None)[-1], name="c")
        result = bus.emit(PRE_TOOL, {"tool": "write_file"})
        self.assertFalse(result.allow)
        self.assertEqual(result.reason, "blocked")
        self.assertEqual(calls, ["a"])

    def test_payload_mutation_threads(self):
        bus = HookBus()
        bus.on(PRE_TOOL, lambda p: HookResult(True, payload={**p, "arguments": {"path": "safe"}}), name="rewrite")
        result = bus.emit(PRE_TOOL, {"tool": "read_file", "arguments": {"path": "../../etc"}})
        self.assertTrue(result.allow)
        self.assertEqual(result.payload["arguments"]["path"], "safe")

    def test_hook_exception_fails_closed(self):
        bus = HookBus()
        bus.on(PRE_TOOL, lambda p: 1 / 0, name="broken")
        result = bus.emit(PRE_TOOL, {})
        self.assertFalse(result.allow)
        self.assertIn("ZeroDivisionError", result.reason)

    def test_deny_paths(self):
        hook = deny_paths((".env", "secrets"))
        self.assertFalse(hook({"path": ".env"}).allow)
        self.assertFalse(hook({"path": "secrets/key"}).allow)
        self.assertIsNone(hook({"path": "src/app.py"}))

    def test_redact_secrets(self):
        hook = redact_secrets()
        result = hook({"content": "key=sk-abcdefghijklmnop1234 end"})
        self.assertNotIn("sk-abcdefghijklmnop1234", result.payload["content"])
        self.assertIn("[REDACTED]", result.payload["content"])

    def test_unknown_event_rejected(self):
        with self.assertRaises(ValueError):
            HookBus().on("not_an_event", lambda p: None)


class InstructionTests(unittest.TestCase):
    def test_root_and_subdir_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text("root rule")
            sub = root / "pkg"
            sub.mkdir()
            (sub / "AGENTS.md").write_text("pkg rule")
            found = discover(root, start=sub)
            texts = [i.text for i in found.items]
            self.assertEqual(texts, ["root rule", "pkg rule"])
            rendered = found.render()
            self.assertLess(rendered.index("root rule"), rendered.index("pkg rule"))

    def test_no_files_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(discover(Path(tmp)).render(), "")


if __name__ == "__main__":
    unittest.main()
