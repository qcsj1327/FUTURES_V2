from __future__ import annotations

import inspect
from pathlib import Path

from app.runtime import Runtime


def _helper_name() -> str:
    return "run_market" + "_once"


def test_run_market_once_is_documented_as_noncanonical_helper() -> None:
    doc = inspect.getdoc(Runtime.run_market_once) or ""

    assert "Non-canonical" in doc
    assert "local/research helper" in doc
    assert "UniverseRuntime.run_tick()" in doc
    assert "production" in doc.lower()
    assert "daemon" in doc.lower()


def test_production_daemon_and_projection_paths_do_not_call_run_market_once() -> None:
    needle = _helper_name()
    checked_roots = [
        Path("app/orchestration"),
        Path("scripts"),
        Path("web"),
        Path("tools"),
    ]

    offenders: list[str] = []
    for root in checked_roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in {".py", ".sh"}:
                continue
            text = path.read_text(encoding="utf-8")
            if needle in text:
                offenders.append(str(path))

    assert offenders == []


def test_contract_tests_do_not_use_run_market_once_as_standard_entrypoint() -> None:
    needle = _helper_name()
    this_file = Path(__file__).resolve()
    offenders: list[str] = []
    for path in sorted(Path("tests/contracts").rglob("*.py")):
        if path.resolve() == this_file:
            continue
        text = path.read_text(encoding="utf-8")
        if needle in text:
            offenders.append(str(path))

    assert offenders == []
