from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from adapters.marketdata.tqkq_market_data import set_tqkq_api_factory_override
from core.execution.lifecycle_reasons import EXPIRED, ORDER_SUBMITTED
from scripts.run_plan import main as run_plan_main


@dataclass
class _Quote:
    last_price: float = 450.0
    volume: float = 1000.0
    datetime: str = "2026-05-04 10:00:00.000000"
    price_tick: float = 0.2
    volume_multiple: float = 1000.0


class _Api:
    def __init__(self) -> None:
        self.q = _Quote()

    def get_quote(self, _sym: str) -> Any:
        return self.q

    def wait_update(self, deadline: float | None = None) -> bool:
        _ = deadline
        return True

    def close(self) -> None:
        return


def _events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_tqkq_sim_no_fill_expires(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TQKQ_USER", "fake_user")
    monkeypatch.setenv("TQKQ_PASS", "fake_pass")
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.tqkq_sim_expire.json"

    set_tqkq_api_factory_override(lambda: _Api())
    try:
        assert (
            run_plan_main(["--config", str(cfg), "--runtime-id", "rt_tqkq_expire", "--clean"])
            == 0
        )
    finally:
        set_tqkq_api_factory_override(None)

    path = tmp_path / "data" / "store" / "live" / "rt_tqkq_expire" / "order_lifecycle_events.jsonl"
    events = _events(path)
    statuses = {str(e["status"]) for e in events}
    reasons = {str(e["reason"]) for e in events if isinstance(e.get("reason"), str)}

    assert "SUBMITTED" in statuses
    assert "EXPIRED" in statuses
    assert ORDER_SUBMITTED in reasons
    assert EXPIRED in reasons
