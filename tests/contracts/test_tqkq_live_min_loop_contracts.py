from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from adapters.broker.tqkq_live_broker import TqKqLiveBroker
from adapters.marketdata.base import MarketDataAdapter, MarketQuote
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime import Runtime
from app.runtime_config import RuntimeConfig
from config.loader import load_plan
from core.instruments.resolver import InstrumentResolver
from core.instruments.roll_policy import RollPolicy
from domain.enums import Decision, PositionSide, Side, SignalStrength
from domain.signal import SignalDecision
from scripts.run_plan import main as run_plan_main
from web.api.events import get_run_events


class _FakeMarketData(MarketDataAdapter):
    def get_last_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(symbol=symbol, price=450.0, volume=1000.0, ts=1)


@dataclass
class _NativeOrder:
    status: str = "SUBMITTED"
    filled_quantity: float = 0.0
    remaining_quantity: float = 1.0
    avg_fill_price: float | None = None


class _FillApi:
    def __init__(self) -> None:
        self.order = _NativeOrder()
        self.poll_count = 0

    def insert_order(self, **_kwargs: object) -> _NativeOrder:
        return self.order

    def wait_update(self, deadline: float | None = None) -> bool:
        _ = deadline
        self.poll_count += 1
        if self.poll_count == 1:
            self.order.status = "PARTIAL"
            self.order.filled_quantity = 0.25
            self.order.remaining_quantity = 0.75
            self.order.avg_fill_price = 450.0
        else:
            self.order.status = "FILLED"
            self.order.filled_quantity = 1.0
            self.order.remaining_quantity = 0.0
            self.order.avg_fill_price = 450.0
        return True


def _events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_tqkq_live_min_loop_dryrun_expires_and_web_events_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = (
        Path(__file__).resolve().parents[2]
        / "plans"
        / "dev.tqkq_live_dryrun_min_loop.json"
    )
    rid = "rt_tqkq_live_min_loop"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    base = tmp_path / "data" / "store" / "live" / rid
    lifecycle = _events(base / "order_lifecycle_events.jsonl")
    statuses = {event.get("status") for event in lifecycle}
    assert {"SUBMITTED", "EXPIRED"}.issubset(statuses)

    portfolio = base / "portfolio_snapshots.jsonl"
    assert portfolio.exists()
    assert portfolio.read_text(encoding="utf-8").strip()

    response = get_run_events(
        runtime_id=rid,
        env="live",
        event_type="order_lifecycle",
        store_root=tmp_path / "data" / "store",
        tail=100,
    )
    assert response["timeline_filtered_total"] == len(lifecycle)
    assert all(event["event_type"] == "order_lifecycle" for event in response["timeline"])


def test_tqkq_live_submit_mode_live_requires_confirm_contract(tmp_path: Path) -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "plans"
        / "dev.tqkq_live_dryrun_min_loop.json"
    )
    plan_path = tmp_path / "live_without_confirm.json"
    plan_path.write_text(
        source.read_text(encoding="utf-8").replace(
            '"submit_mode": "dry_run"',
            '"submit_mode": "live"',
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="confirm_live must be true"):
        load_plan(plan_path, runtime_id="rt_live_without_confirm")


def test_lifecycle_cost_fields_present_when_fill_contract() -> None:
    store = MemoryDataStore(env="live", runtime_id="rt_tqkq_live_cost")
    market_data = _FakeMarketData()
    broker = TqKqLiveBroker(
        market_data=market_data,
        dry_run=False,
        api_factory=lambda: _FillApi(),
    )
    runtime = Runtime(
        config=RuntimeConfig(runtime_id="rt_tqkq_live_cost"),
        market_data=market_data,
        broker=broker,
        datastore=store,
        runtime_id="rt_tqkq_live_cost",
        instrument_resolver=InstrumentResolver(
            roll_policy=RollPolicy(
                mode="fixed_contract",
                contracts={"au": "SHFE.au2406"},
                runtime_id="rt_tqkq_live_cost",
                env="live",
                sink=store,
            )
        ),
    )
    runtime.run(
        SignalDecision(
            decision=Decision.OPEN_LONG,
            side=Side.BUY,
            strength=SignalStrength.STRONG,
            confidence=1.0,
            reason="contract",
            symbol="au",
            instrument_id="au",
            trade_instrument_id="SHFE.au2406",
            position_side=PositionSide.LONG,
            ts=1,
        ),
        strategy_name="contract",
        strategy_impl="contract",
        market_ts=1,
    )
    runtime.poll_order_lifecycle(1)
    runtime.poll_order_lifecycle(2)

    cost_keys = {
        "market_price",
        "raw_fill_price",
        "fill_price",
        "multiplier",
        "tick_size",
        "notional",
        "commission",
        "slippage",
        "cost_total",
        "margin",
    }
    filled_or_partial = [
        event
        for event in store.order_lifecycle_events
        if event.get("status") in {"PARTIAL", "FILLED"}
    ]
    assert filled_or_partial
    assert all(cost_keys.issubset(event.keys()) for event in filled_or_partial)
