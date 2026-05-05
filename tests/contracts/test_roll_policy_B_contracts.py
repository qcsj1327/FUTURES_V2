from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.base import MarketDataAdapter, MarketQuote
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime import Runtime, _PendingOrderContext
from app.runtime_config import RuntimeConfig
from core.execution.lifecycle_reasons import (
    ROLL_CANCEL_PENDING,
    ROLL_CLOSE_POSITION,
    ROLL_COOLDOWN_BLOCK,
)
from core.instruments.resolver import InstrumentResolver
from core.instruments.roll_policy import RollPolicy
from domain.enums import Decision, PositionSide, Side, SignalStrength
from domain.execution import ExecutionOrder
from domain.signal import SignalDecision
from scripts.run_plan import main as run_plan_main


class _StaticMarketData(MarketDataAdapter):
    def get_last_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(symbol=symbol, price=120.0, volume=1000.0, ts=0)


def _open_decision(ts: int = 0) -> SignalDecision:
    return SignalDecision(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        strength=SignalStrength.STRONG,
        confidence=1.0,
        reason="contract",
        symbol="au",
        instrument_id="au",
        trade_instrument_id=None,
        position_side=PositionSide.LONG,
        ts=ts,
    )


def _runtime() -> Runtime:
    store = MemoryDataStore(env="live", runtime_id="rt_roll_B")
    market_data = _StaticMarketData()
    broker = SimulatedBroker(market_data=market_data)
    return Runtime(
        config=RuntimeConfig(runtime_id="rt_roll_B"),
        market_data=market_data,
        broker=broker,
        datastore=store,
        runtime_id="rt_roll_B",
        instrument_resolver=InstrumentResolver(
            roll_policy=RollPolicy(
                mode="fixed_main",
                contracts={"au": "au2506"},
                runtime_id="rt_roll_B",
                env="live",
                sink=store,
                close_on_roll=True,
                cooldown_ticks=2,
                main_contract_schedule={"au": ["au2506", "au2507", "au2507"]},
            )
        ),
    )


def _events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_roll_policy_B_cancels_pending_then_closes_positions_contracts() -> None:
    runtime = _runtime()
    store = runtime.datastore
    assert isinstance(store, MemoryDataStore)

    runtime.run(_open_decision(0), strategy_name="contract", market_ts=0)
    pending_order = ExecutionOrder(
        instrument_id="au",
        trade_instrument_id="au2506",
        side=Side.BUY,
        position_side=PositionSide.LONG,
        quantity=1.0,
        order_type="market",
    )
    runtime._pending_order_contexts["pending_roll"] = _PendingOrderContext(
        order=pending_order,
        strategy_name="contract",
        strategy_impl="contract",
        symbol="au",
        submitted_tick=runtime._tick,
        remaining_quantity=1.0,
    )

    runtime.run(_open_decision(1), strategy_name="contract", market_ts=1)
    runtime.run(_open_decision(1), strategy_name="contract", market_ts=1)

    reasons = {event.get("reason") for event in store.order_lifecycle_events}
    assert ROLL_CANCEL_PENDING in reasons
    assert ROLL_CLOSE_POSITION in reasons


def test_roll_policy_B_blocks_open_during_cooldown_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.roll_min_policy_B.json"
    rid = "rt_roll_B_cooldown"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    base = tmp_path / "data" / "store" / "live" / rid
    lifecycle = _events(base / "order_lifecycle_events.jsonl")
    assert any(event.get("reason") == ROLL_COOLDOWN_BLOCK for event in lifecycle)


def test_roll_policy_B_switches_trade_id_after_flat_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.roll_min_policy_B.json"
    rid = "rt_roll_B_switch"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    base = tmp_path / "data" / "store" / "live" / rid
    roll_events = _events(base / "roll_events.jsonl")
    order_events = _events(base / "order_events.jsonl")
    assert roll_events
    assert any(event.get("to_contract") == "au2507" for event in roll_events)
    assert any(event.get("trade_instrument_id") == "au2507" for event in order_events)
