from __future__ import annotations

from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main


def test_live_submit_guard_requires_runtime_id_token_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = (
        Path(__file__).resolve().parents[2]
        / "plans"
        / "dev.tqkq_live_live_submit_guard_fail.json"
    )

    with pytest.raises(ValueError) as excinfo:
        run_plan_main(["--config", str(cfg), "--runtime-id", "rt_live_guard", "--clean"])

    message = str(excinfo.value)
    assert "submit_mode" in message
    assert "confirm_live" in message
    assert "token_present" in message
    assert "expected_token=runtime_id:rt_live_guard" in message
    assert "actual_token" in message
    assert "wrong-token" not in message
