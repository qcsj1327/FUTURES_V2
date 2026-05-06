from __future__ import annotations

from typing import Any

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.storage.datastore_memory import MemoryDataStore
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
            reason="scope_isolation_contract",
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


def test_dryrun_runtime_writes_do_not_touch_live_store() -> None:
    config = RuntimeConfig()

    live_store = MemoryDataStore(scope="live", runtime_id=config.runtime_id)
    baseline_live = len(live_store.snapshots)

    dryrun_md = FixedMarketData()
    dryrun_broker = SimulatedBroker(dryrun_md)
    dryrun_store = MemoryDataStore(scope="dryrun", runtime_id=config.runtime_id)
    dryrun_runtime = RuntimeFactory.build_runtime(
        config=config,
        market_data=dryrun_md,
        broker=dryrun_broker,
        datastore=dryrun_store,
        scope="dryrun",
    )

    _run_canonical_tick(dryrun_runtime, dryrun_md)

    assert len(live_store.snapshots) == baseline_live
    assert len(dryrun_store.snapshots) == 1
    # fill_events are actual fill facts and must stay isolated to dryrun.
    assert len(live_store.fill_events) == 0
    assert len(dryrun_store.fill_events) == 1
    fill = dryrun_store.fill_events[0]
    assert isinstance(fill, dict)
    assert fill.get("event_type") == "fill"
    for k in ("ts", "runtime_id", "datastore_scope", "strategy_name", "quantity", "fill_price"):
        assert k in fill
    assert fill["datastore_scope"] == "dryrun"
