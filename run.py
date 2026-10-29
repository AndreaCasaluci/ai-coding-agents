#!/usr/bin/env python3
"""Course runner — works without make.

    python3 run.py test       run the unit test suite
    python3 run.py labs       run every lab script in order
    python3 run.py demo       run the agent against this repo
    python3 run.py capstone   run the capstone evals
    python3 run.py lint       compile-check every Python file
    python3 run.py clean      remove caches and scratch output
"""

from __future__ import annotations

import compileall
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def test() -> int:
    return subprocess.call([PY, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"], cwd=ROOT)


def labs() -> int:
    scripts = sorted((ROOT / "labs").glob("L*.py"))
    if not scripts:
        print("no labs found")
        return 1
    for script in scripts:
        print(f"\n── {script.relative_to(ROOT)}")
        code = subprocess.call([PY, str(script)], cwd=ROOT)
        if code != 0:
            print(f"lab failed: {script} (exit {code})")
            return code
    print(f"\nall {len(scripts)} labs passed")
    return 0


def demo() -> int:
    return subprocess.call(
        [PY, "-m", "mini_agent", "list the files in this repo", "--audit", ""], cwd=ROOT
    )


def capstone() -> int:
    return subprocess.call([PY, "-m", "capstone.repo_doctor", "--eval"], cwd=ROOT)


def lint() -> int:
    ok = True
    for folder in ("mini_agent", "labs", "capstone", "tests"):
        target = ROOT / folder
        if target.exists():
            ok = compileall.compile_dir(str(target), quiet=1) and ok
    print("compile ok" if ok else "compile failed")
    return 0 if ok else 1


def clean() -> int:
    for path in ROOT.rglob("__pycache__"):
        shutil.rmtree(path, ignore_errors=True)
    for name in (".mini_agent", "sandbox", ".pytest_cache"):
        shutil.rmtree(ROOT / name, ignore_errors=True)
    print("cleaned")
    return 0


COMMANDS = {
    "test": test,
    "labs": labs,
    "demo": demo,
    "capstone": capstone,
    "lint": lint,
    "clean": clean,
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(__doc__)
        return 0
    command = COMMANDS.get(argv[0])
    if command is None:
        print(f"unknown command: {argv[0]}\n")
        print(__doc__)
        return 2
    return command()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
