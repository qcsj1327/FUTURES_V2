from __future__ import annotations

import json
from pathlib import Path

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.base import MarketDataAdapter, MarketQuote, base_symbol
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
from app.universe_runtime import UniverseRuntime
from core.instruments.resolver import InstrumentResolver
from core.instruments.roll_policy import RollPolicy
from core.signal_router.router import RouterConfig
from scripts.run_plan import main as run_plan_main
from strategies.registry import StrategyRegistry
from strategies.strategy_set import StrategyEntry, StrategySet
from web.api.events import get_run_events

SYMBOLS = ["au", "ag", "cu", "rb", "zn"]


class ScheduledMarketData(MarketDataAdapter):
    def __init__(self) -> None:
        self.tick = 0
        self._prices = [
            {"au": 101.0, "ag": 101.0, "cu": 101.0, "rb": 101.0, "zn": 101.0},
            {"au": 101.0, "ag": 101.0, "cu": 101.0, "rb": 120.0, "zn": 125.0},
            {"au": 101.0, "ag": 101.0, "cu": 101.0, "rb": 130.0, "zn": 135.0},
            {"au": 101.0, "ag": 101.0, "cu": 101.0, "rb": 140.0, "zn": 145.0},
            {"au": 101.0, "ag": 101.0, "cu": 101.0, "rb": 150.0, "zn": 155.0},
        ]

    def get_last_quote(self, symbol: str) -> MarketQuote:
        sym = base_symbol(symbol)
        idx = min(self.tick, len(self._prices) - 1)
        return MarketQuote(symbol=sym, price=self._prices[idx][sym], volume=1000.0, ts=self.tick)

    def get_last_quotes(self, symbols: list[str]) -> dict[str, MarketQuote]:
        return {s: self.get_last_quote(s) for s in symbols}

    def advance(self) -> None:
        self.tick += 1


def _build_universe() -> tuple[UniverseRuntime, MemoryDataStore]:
    md = ScheduledMarketData()
    broker = SimulatedBroker(md, fill_delay_ticks=2, partial_fill_ratio=0.5)
    store = MemoryDataStore(env="live", runtime_id="rt_lifecycle")
    resolver = InstrumentResolver(
        roll_policy=RollPolicy(
            mode="fixed_contract",
            contracts={s: f"SHFE.{s}2406" for s in SYMBOLS},
            runtime_id="rt_lifecycle",
            env="live",
            sink=store,
        )
    )
    executor = RuntimeFactory.build_live_runtime(
        config=RuntimeConfig(runtime_id="rt_lifecycle", default_quantity=1.0),
        runtime_id="rt_lifecycle",
        market_data=md,
        broker=broker,
        datastore=store,
        instrument_resolver=resolver,
    )
    strategy = StrategyRegistry.create(name="simple_strategy", params={})
    strategy_set = StrategySet(
        [
            StrategyEntry(
                name="simple_strategy",
                strategy=strategy,
                symbols=SYMBOLS,
                priority=10,
                params={},
            )
        ]
    )
    return (
        UniverseRuntime(
            executor=executor,
            market_data=md,
            universe_symbols=SYMBOLS,
            strategy_set=strategy_set,
            strategy_priorities={"simple_strategy": 10},
            strategy_weights={"simple_strategy": 1.0},
            router_config=RouterConfig(mode="priority"),
            active_top_n=3,
            rank_window=1,
            rank_metric="quote_momentum_volume",
            rank_refresh_every=1,
            rank_emit_events=1,
        ),
        store,
    )


def test_pending_orders_continue_after_symbol_drops_out_of_topn() -> None:
    universe, store = _build_universe()

    for _ in range(5):
        universe.run_tick()

    active_by_tick = {
        ev["ts"]: {item["symbol"] for item in ev["scores"]} for ev in store.rank_events
    }
    assert "au" in active_by_tick[0]
    assert "au" not in active_by_tick[2]

    au_orders = [ev for ev in store.order_events if ev["symbol"] == "au"]
    assert len(au_orders) == 1

    au_lifecycle = [ev for ev in store.order_lifecycle_events if ev["symbol"] == "au"]
    assert [ev["status"] for ev in au_lifecycle[:3]] == [
        "submitted",
        "partially_filled",
        "filled",
    ]
    assert au_lifecycle[-1]["ts"] >= 3
    assert au_lifecycle[-1]["status"] == "filled"

    au_fills = [ev for ev in store.fill_events if ev["symbol"] == "au"]
    assert len(au_fills) == 1
    assert au_fills[0]["success"] is True


def _write_lifecycle_plan(tmp_path: Path, runtime_id: str) -> Path:
    data_root = tmp_path / "data"
    plan_path = tmp_path / f"{runtime_id}.json"
    plan = {
        "schema_version": 1,
        "env": "dev",
        "adapters": {
            "market_data": {
                "mode": "simulated_v2",
                "params": {
                    "seed": 17,
                    "drift": 0.0001,
                    "vol": 0.01,
                    "start_prices": {s: 1000.0 for s in SYMBOLS},
                    "start_volumes": {s: 1000.0 for s in SYMBOLS},
                },
            },
            "broker": {
                "mode": "simulated",
                "params": {"fill_delay_ticks": 2, "partial_fill_ratio": 0.5},
            },
        },
        "universe": {"symbols": SYMBOLS},
        "strategies": [
            {
                "name": "simple_strategy",
                "params": {},
                "symbols": SYMBOLS,
                "priority": 10,
                "weight": 1.0,
            }
        ],
        "instruments": {
            "roll_policy": {
                "mode": "fixed_contract",
                "contracts": {s: f"SHFE.{s}2406" for s in SYMBOLS},
            }
        },
        "runtime": {
            "ticks_live": 8,
            "ticks_sandbox": 0,
            "default_quantity": 1.0,
            "active_top_n": 3,
            "rank_window": 2,
            "rank_metric": "quote_momentum_volume",
            "rank_refresh_every": 1,
            "rank_emit_events": 1,
        },
        "datastore": {
            "store_root": str(data_root / "store"),
            "artifacts_root": str(data_root / "artifacts"),
            "approved_dir": str(data_root / "artifacts" / "approved"),
            "decisions_dir": str(data_root / "artifacts" / "decisions"),
            "summaries_dir": str(data_root / "artifacts" / "summaries"),
            "manifests_dir": str(data_root / "artifacts" / "manifests"),
        },
        "promotion": {
            "min_events": 1,
            "min_success_rate_improvement": -1.0,
            "max_consecutive_failures": 99,
        },
        "router": {"mode": "priority", "tie_breaker": "priority"},
    }
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan_path


def test_web_events_api_filters_order_lifecycle(tmp_path: Path) -> None:
    rid = "rt_lifecycle_web"
    plan_path = _write_lifecycle_plan(tmp_path, rid)

    assert run_plan_main(["--config", str(plan_path), "--runtime-id", rid, "--clean"]) == 0

    payload = get_run_events(
        runtime_id=rid,
        env="live",
        store_root=tmp_path / "data" / "store",
        event_type="order_lifecycle",
        tail=100,
    )
    assert payload["order_lifecycle_events"]
    assert payload["timeline"]
    assert all(ev["event_type"] == "order_lifecycle" for ev in payload["timeline"])
