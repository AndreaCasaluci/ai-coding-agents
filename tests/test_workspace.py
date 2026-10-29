import tempfile
import unittest
from pathlib import Path

from mini_agent.workspace import Workspace, WorkspaceError


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Workspace(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_write_read_roundtrip(self):
        self.ws.write("src/a.txt", "hello")
        self.assertEqual(self.ws.read("src/a.txt"), "hello")

    def test_path_traversal_blocked(self):
        with self.assertRaises(WorkspaceError):
            self.ws.resolve("../outside.txt")

    def test_absolute_path_outside_blocked(self):
        with self.assertRaises(WorkspaceError):
            self.ws.read("/etc/passwd")

    def test_symlink_escape_blocked(self):
        outside = Path(tempfile.mkdtemp()) / "secret.txt"
        outside.write_text("nope")
        link = Path(self.tmp.name) / "link"
        link.symlink_to(outside)
        with self.assertRaises(WorkspaceError):
            self.ws.read("link")

    def test_edit_requires_unique_match(self):
        self.ws.write("f.txt", "a\na\n")
        with self.assertRaises(WorkspaceError):
            self.ws.edit("f.txt", "a", "b")
        self.ws.edit("f.txt", "a\na", "b\na")
        self.assertEqual(self.ws.read("f.txt"), "b\na\n")

    def test_edit_missing_string(self):
        self.ws.write("f.txt", "abc")
        with self.assertRaises(WorkspaceError):
            self.ws.edit("f.txt", "zzz", "x")

    def test_read_only_refuses_writes(self):
        self.ws.read_only = True
        with self.assertRaises(WorkspaceError):
            self.ws.write("x.txt", "nope")

    def test_read_line_range_is_numbered(self):
        self.ws.write("f.txt", "one\ntwo\nthree\n")
        out = self.ws.read("f.txt", start=2, end=3)
        self.assertIn("two", out)
        self.assertIn("three", out)
        self.assertNotIn("one", out)

    def test_search_reports_location(self):
        self.ws.write("a.py", "import os\nprint('hi')\n")
        hits = self.ws.search("import")
        self.assertIn("a.py:1", hits)

    def test_large_file_truncated(self):
        self.ws.write("big.txt", "x" * 50_000)
        self.assertIn("truncated", self.ws.read("big.txt"))


if __name__ == "__main__":
    unittest.main()
