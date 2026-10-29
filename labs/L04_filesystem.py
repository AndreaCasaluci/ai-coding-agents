"""Lab 04 — The filesystem: jails, anchors, and staleness.

Run: python3 labs/L04_filesystem.py

Goal: reproduce the path escapes and stale-copy bugs that damage real repos.
"""

from __future__ import annotations

from _helpers import note, section, temp_ws

from mini_agent import Workspace, WorkspaceError

ORIGINAL = """\
def parse_date(s):
    return datetime.strptime(s, FMT)
"""


def main() -> None:
    with temp_ws("fs") as tmp:
        ws = Workspace(tmp)
        ws.write("src/dates.py", ORIGINAL)

        section("1. THE PATH JAIL")
        for path in ("src/dates.py", "../outside.txt", "/etc/passwd", "src/../../escape.txt"):
            try:
                resolved = ws.resolve(path)
                print(f"  ALLOWED  {path!r:<24} -> {resolved}")
            except WorkspaceError as exc:
                print(f"  BLOCKED  {path!r:<24} -> {exc}")

        section("2. SYMLINKS FOLLOW BEFORE THE CHECK")
        outside = ws.root.parent / "outside-secret.txt"
        outside.write_text("host secret")
        (ws.root / "link").symlink_to(outside)
        try:
            ws.read("link")
            print("  ALLOWED (bad)")
        except WorkspaceError as exc:
            print(f"  BLOCKED  'link' -> {exc}")
        note("resolve() follows the symlink, so containment is checked on the real path.")
        note("This is a correctness boundary, not a security boundary (lesson 12).")

        section("3. UNIQUE-ANCHOR EDITING")
        ws.write("src/dates.py", "a\nb\nb\n")
        try:
            ws.edit("src/dates.py", "b", "c")
        except WorkspaceError as exc:
            print(f"  AMBIGUOUS -> {exc}")
        note("Two matches: the harness refuses rather than guessing which one.")
        ws.edit("src/dates.py", "b\nb", "b\nc")
        print("  after unique edit:", ws.read("src/dates.py").split())

        section("4. TRUNCATION IS ANNOUNCED")
        ws.write("big.log", "line of log output\n" * 5_000)
        out = ws.read("big.log")
        print(f"  returned {len(out)} chars")
        print("  " + out.splitlines()[-1])
        note("Without the marker the model believes it read the whole file.")

        section("5. THE STALE COPY BUG")
        ws.write("src/dates.py", ORIGINAL)
        stale_copy = ws.read("src/dates.py")          # model reads v1
        ws.write("src/dates.py", ORIGINAL + "\ndef helper():\n    return 42\n")  # user edits to v2

        print("  disk now has a helper the model never saw.")
        ws.write("src/dates.py", stale_copy.replace("return datetime", "if not s:\n        raise ValueError()\n    return datetime"))
        print("  after write_file(stale_copy):")
        print("   ", "helper present?", "def helper" in ws.read("src/dates.py"))
        note("The rewrite silently destroyed the user's change. Blast radius: the file.")

        section("6. THE SAME MISTAKE WITH AN EDIT")
        ws.write("src/dates.py", ORIGINAL)
        ws.write("src/dates.py", ORIGINAL + "\ndef helper():\n    return 42\n")
        try:
            ws.edit("src/dates.py", "return datetime.strptime(s, FMT)", "if not s:\n        raise ValueError()\n    return datetime.strptime(s, FMT)")
            print("  edit applied; helper present?", "def helper" in ws.read("src/dates.py"))
        except WorkspaceError as exc:
            print(f"  edit failed loudly -> {exc}")

        section("7. TRY IT AGAIN, CORRECTLY")
        ws.write("src/dates.py", ORIGINAL + "\ndef helper():\n    return 42\n")
        ws.edit("src/dates.py", "def parse_date(s):", "def parse_date(s):\n    if not s:\n        raise ValueError(\"empty date\")")
        print(ws.read("src/dates.py"))
        note("Small anchor, bounded blast radius, user's change preserved.")


if __name__ == "__main__":
    main()
