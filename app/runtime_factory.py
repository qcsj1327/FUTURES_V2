from __future__ import annotations

from pathlib import Path

from adapters.broker.base import BrokerAdapter
from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.base import MarketDataAdapter
from adapters.marketdata.live_market_data import LiveFileMarketData
from adapters.storage.datastore_fs import JSONLFileDataStore
from app.runtime import Runtime
from app.runtime_config import RuntimeConfig
from core.instruments.calendar import TradingCalendar
from core.instruments.resolver import InstrumentResolver
from core.services.runtime.datastore import DataStore
from core.state.state_engine import StateEngine
from strategies.base.strategy import Strategy


class RuntimeFactory:
    @staticmethod
    def build_runtime(
        *,
        config: RuntimeConfig | None,
        market_data: MarketDataAdapter,
        broker: BrokerAdapter,
        state: StateEngine | None = None,
        strategy: Strategy | None = None,
        scope: str = "live",
        datastore: DataStore | None = None,
        runtime_id: str | None = None,
        trading_calendar: TradingCalendar | None = None,
        instrument_resolver: InstrumentResolver | None = None,
    ) -> Runtime:
        return Runtime(
            config,
            market_data=market_data,
            broker=broker,
            state=state,
            strategy=strategy,
            scope=scope,
            datastore=datastore,
            runtime_id=runtime_id,
            trading_calendar=trading_calendar,
            instrument_resolver=instrument_resolver,
        )

    @staticmethod
    def build_live_runtime(
        *,
        config: RuntimeConfig,
        market_data: MarketDataAdapter,
        broker: BrokerAdapter,
        state: StateEngine | None = None,
        strategy: Strategy | None = None,
        datastore: DataStore | None = None,
        runtime_id: str | None = None,
        trading_calendar: TradingCalendar | None = None,
        instrument_resolver: InstrumentResolver | None = None,
    ) -> Runtime:
        rid = runtime_id or config.runtime_id
        if datastore is None:
            datastore = JSONLFileDataStore(
                root_dir=Path("data/store/live"),
                scope="live",
                runtime_id=rid,
            )
        return RuntimeFactory.build_runtime(
            config=config,
            market_data=market_data,
            broker=broker,
            state=state,
            strategy=strategy,
            scope="live",
            datastore=datastore,
            runtime_id=rid,
            trading_calendar=trading_calendar,
            instrument_resolver=instrument_resolver,
        )

    @staticmethod
    def build_local_runtime(
        config: RuntimeConfig | None = None,
        *,
        slippage_rate: float = 0.0,
        order_id_prefix: str = "LOCAL-SIM",
        reject_next_order: bool = False,
        rejected_symbols: set[str] | None = None,
        reject_above_quantity: float | None = None,
        fill_ratio: float = 1.0,
        state: StateEngine | None = None,
        strategy: Strategy | None = None,
        datastore: DataStore | None = None,
        runtime_id: str | None = None,
        trading_calendar: TradingCalendar | None = None,
        instrument_resolver: InstrumentResolver | None = None,
    ) -> Runtime:
        market_data = LiveFileMarketData(Path("plans/prices.json"))
        broker = SimulatedBroker(
            market_data,
            slippage_rate=slippage_rate,
            order_id_prefix=order_id_prefix,
            reject_next_order=reject_next_order,
            rejected_symbols=rejected_symbols,
            reject_above_quantity=reject_above_quantity,
            fill_ratio=fill_ratio,
        )
        if config is None:
            base_id = RuntimeConfig().runtime_id
        else:
            base_id = config.runtime_id
        rid = runtime_id or base_id
        if datastore is None:
            datastore = JSONLFileDataStore(
                root_dir=Path("data/store/local"),
                scope="local",
                runtime_id=rid,
            )
        return RuntimeFactory.build_runtime(
            config=config,
            market_data=market_data,
            broker=broker,
            state=state,
            strategy=strategy,
            scope="local",
            datastore=datastore,
            runtime_id=rid,
            trading_calendar=trading_calendar,
            instrument_resolver=instrument_resolver,
        )
