from __future__ import annotations

from app.auto_runner import AutoRunner
from app.runtime import Runtime


def test_auto_runner() -> None:
    runtime = Runtime()
    runner = AutoRunner(runtime)

    runner.run_once()

    assert runtime.orders_submitted >= 0
