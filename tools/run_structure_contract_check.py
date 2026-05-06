from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Check:
    name: str
    command: tuple[str, ...]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _python_for_checks(repo_root: Path) -> str:
    venv_python = repo_root / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _checks(repo_root: Path) -> tuple[Check, ...]:
    python = _python_for_checks(repo_root)
    return (
        Check(
            name="contracts",
            command=(python, "-m", "pytest", "tests/contracts", "-q"),
        ),
        Check(
            name="tests",
            command=(python, "-m", "pytest", "tests", "-q"),
        ),
        Check(
            name="mypy",
            command=(
                python,
                "-m",
                "mypy",
                "app",
                "core",
                "adapters",
                "optimize",
                "web",
                "tests",
            ),
        ),
        Check(
            name="ruff",
            command=(
                python,
                "-m",
                "ruff",
                "check",
                "app",
                "core",
                "adapters",
                "optimize",
                "web",
                "tests",
            ),
        ),
        Check(name="git-diff-check", command=("git", "diff", "--check")),
        Check(name="web-ui-js", command=("node", "--check", "web/ui/app.js")),
    )


def _run_check(check: Check, *, cwd: Path) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            check.command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
        return {
            "name": check.name,
            "command": list(check.command),
            "returncode": completed.returncode,
            "duration_seconds": round(time.perf_counter() - started, 3),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except FileNotFoundError as exc:
        return {
            "name": check.name,
            "command": list(check.command),
            "returncode": 127,
            "duration_seconds": round(time.perf_counter() - started, 3),
            "stdout": "",
            "stderr": str(exc),
        }


def _print_text_report(results: list[dict[str, Any]]) -> None:
    print("Structure contract freeze check")
    for result in results:
        status = "PASS" if result["returncode"] == 0 else "FAIL"
        print(
            f"[{status}] {result['name']} "
            f"({result['duration_seconds']:.3f}s): {' '.join(result['command'])}"
        )
        if result["returncode"] != 0:
            stdout = str(result["stdout"]).strip()
            stderr = str(result["stderr"]).strip()
            if stdout:
                print(stdout)
            if stderr:
                print(stderr, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_structure_contract_check",
        description="Run the read-only structure contract freeze validation suite.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable validation report.",
    )
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    results = [_run_check(check, cwd=repo_root) for check in _checks(repo_root)]
    ok = all(result["returncode"] == 0 for result in results)
    payload = {
        "ok": ok,
        "repo_root": str(repo_root),
        "checks": results,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text_report(results)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
