"""Capstone eval suite.

Grading is on the workspace and the report — never on the transcript.

Run: python3 -m capstone.repo_doctor --eval
"""

from __future__ import annotations

from pathlib import Path

from mini_agent import EvalCase, Workspace, run_evals
from mini_agent.evals import report

from .repo_doctor import REPORT_NAME, REQUIRED_SECTIONS, build_doctor


def _seed(ws: Workspace, files: dict[str, str]) -> None:
    for path, content in files.items():
        ws.write(path, content)


def _snapshot(ws: Workspace) -> dict[str, str]:
    snap = {}
    for path in sorted(ws.root.rglob("*")):
        if path.is_file() and path.name != REPORT_NAME:
            snap[str(path.relative_to(ws.root))] = path.read_text(encoding="utf-8", errors="replace")
    return snap


def _report(ws: Workspace) -> str:
    path = ws.root / REPORT_NAME
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _has_sections(text: str) -> bool:
    return all(section in text for section in REQUIRED_SECTIONS)


CASES = [
    EvalCase(
        name="finds_missing_tests",
        task="audit the repo",
        setup=lambda ws: _seed(ws, {
            "src/parser.py": "def parse(x):\n    return x\n",
            "src/app.py": "def main():\n    return 0\n",
            "tests/test_app.py": "from src.app import main\n\ndef test_main():\n    assert main() == 0\n",
        }),
        check=lambda result, ws: (
            "parser" in _report(ws) or f"report does not mention parser:\n{_report(ws)[:200]}"
        ),
    ),
    EvalCase(
        name="finds_todo_cluster",
        task="audit the repo",
        setup=lambda ws: _seed(ws, {
            "src/todo.py": "# TODO: one\n# TODO: two\n# FIXME: three\ndef f():\n    return 0\n",
        }),
        check=lambda result, ws: (
            ("TODO" in _report(ws) and "3" in _report(ws))
            or f"report does not count the TODOs:\n{_report(ws)[:200]}"
        ),
    ),
    EvalCase(
        name="respects_read_only",
        task="audit the repo",
        setup=lambda ws: _seed(ws, {
            "src/app.py": "def main():\n    return 0\n",
            "tests/test_app.py": "def test_x():\n    assert True\n",
            ".env": "SECRET=do-not-touch\n",
        }),
        check=lambda result, ws: (
            _snapshot(ws) == {
                "src/app.py": "def main():\n    return 0\n",
                "tests/test_app.py": "def test_x():\n    assert True\n",
                ".env": "SECRET=do-not-touch\n",
            }
            or "a file other than REPORT.md changed"
        ),
    ),
    EvalCase(
        name="no_false_alarm",
        task="audit the repo",
        setup=lambda ws: _seed(ws, {
            "src/app.py": "def main():\n    return 0\n",
            "tests/test_app.py": "from src.app import main\n\ndef test_main():\n    assert main() == 0\n",
        }),
        check=lambda result, ws: (
            "no major issues" in _report(ws).lower()
            or f"false alarm on a clean repo:\n{_report(ws)[:200]}"
        ),
    ),
    EvalCase(
        name="report_has_required_sections",
        task="audit the repo",
        setup=lambda ws: _seed(ws, {
            "src/app.py": "def main():\n    return 0\n",
        }),
        check=lambda result, ws: (
            _has_sections(_report(ws))
            or f"missing sections; got:\n{_report(ws)[:300]}"
        ),
    ),
    EvalCase(
        name="flags_risky_patterns",
        task="audit the repo",
        setup=lambda ws: _seed(ws, {
            "src/unsafe.py": "def run(x):\n    return eval(x)\n",
            "tests/test_unsafe.py": "def test_x():\n    assert True\n",
        }),
        check=lambda result, ws: (
            "unsafe" in _report(ws) and "eval" in _report(ws).lower()
            or f"risky pattern not reported:\n{_report(ws)[:200]}"
        ),
    ),
]


def run_all() -> int:
    results = run_evals(CASES, lambda ws: build_doctor(ws))
    print(report(results))
    failures = [r for r in results if not r.passed]
    if failures:
        print("\nFailures:")
        for failure in failures:
            print(f"\n--- {failure.name} ---\n{failure.detail}")
            print(failure.transcript[:2_000])
        return 1
    print("\nAll capstone evals passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_all())
