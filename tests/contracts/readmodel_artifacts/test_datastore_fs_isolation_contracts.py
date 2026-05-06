from __future__ import annotations

from pathlib import Path
from typing import Any

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.storage.datastore_fs import JSONLFileDataStore
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
from app.universe_runtime import UniverseRuntime
from core.services.marketdata.types import MarketDataAdapter, MarketQuote
from core.signal_router.router import RouterConfig
from domain.enums import Decision, PositionSide, Side, SignalStrength
from domain.signal import SignalDecision
from strategies.base.strategy import Strategy
from strategies.strategy_set import StrategyEntry, StrategySet


class FixedMarketData(MarketDataAdapter):
    def get_last_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(symbol=symbol, price=101.0, volume=1000.0, ts=1)


class OpenLongStrategy(Strategy):
    def generate(self, symbol: str, quote: MarketQuote) -> SignalDecision:
        return SignalDecision(
            decision=Decision.OPEN_LONG,
            side=Side.BUY,
            strength=SignalStrength.STRONG,
            confidence=1.0,
            reason="fs_scope_isolation_contract",
            symbol=symbol,
            instrument_id=symbol,
            trade_instrument_id="SHFE.au2606",
            position_side=PositionSide.LONG,
            ts=quote.ts,
            bar_ts=quote.ts,
        )


def _run_canonical_tick(runtime: Any, market_data: MarketDataAdapter) -> None:
    universe = UniverseRuntime(
        executor=runtime,
        market_data=market_data,
        universe_symbols=["au"],
        strategy_set=StrategySet(
            [
                StrategyEntry(
                    name="open_long",
                    strategy=OpenLongStrategy(),
                    symbols=["au"],
                    priority=1,
                    params={},
                )
            ]
        ),
        strategy_priorities={"open_long": 1},
        strategy_weights={"open_long": 1.0},
        router_config=RouterConfig(),
    )
    universe.run_tick()


def test_fs_datastore_isolation_live_not_touched_by_dryrun(tmp_path: Path) -> None:
    config = RuntimeConfig()

    md = FixedMarketData()
    broker = SimulatedBroker(md)

    dryrun_store = JSONLFileDataStore(
        root_dir=tmp_path / "dryrun",
        scope="dryrun",
        runtime_id=config.runtime_id,
    )
    dryrun_runtime = RuntimeFactory.build_runtime(
        config=config,
        market_data=md,
        broker=broker,
        datastore=dryrun_store,
        scope="dryrun",
    )

    _run_canonical_tick(dryrun_runtime, md)

    live_snap = tmp_path / "live" / config.runtime_id / "portfolio_snapshots.jsonl"
    dryrun_snap = tmp_path / "dryrun" / config.runtime_id / "portfolio_snapshots.jsonl"

    # dryrun writes must not create/touch live files.
    assert not live_snap.exists()
    assert dryrun_snap.exists()
    assert dryrun_snap.read_text(encoding="utf-8").strip() != ""


def test_loading_missing_snapshot_does_not_create_runtime_dir(tmp_path: Path) -> None:
    store = JSONLFileDataStore(root_dir=tmp_path / "live", scope="live", runtime_id="rt_empty")

    assert store.load_latest_portfolio_snapshot(scope="live") is None
    assert not (tmp_path / "live" / "rt_empty").exists()
