from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy

from adapters.broker.base import BrokerAdapter
from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.base import MarketDataAdapter
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from app.runtime import Runtime
from app.runtime_config import RuntimeConfig
from core.services.runtime.datastore import DataStore
from core.services.runtime.state_clone import clone_state_engine
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
        environment: str = "live",
        datastore: DataStore | None = None,
    ) -> Runtime:
        return Runtime(
            config,
            market_data=market_data,
            broker=broker,
            state=state,
            strategy=strategy,
            environment=environment,
            datastore=datastore,
        )

    @staticmethod
    def build_live_runtime(
        *,
        config: RuntimeConfig,
        market_data: MarketDataAdapter,
        broker: BrokerAdapter,
        state: StateEngine | None = None,
        strategy: Strategy | None = None,
        environment: str = "live",
        datastore: DataStore | None = None,
    ) -> Runtime:
        return RuntimeFactory.build_runtime(
            config=config,
            market_data=market_data,
            broker=broker,
            state=state,
            strategy=strategy,
            environment=environment,
            datastore=datastore,
        )

    @staticmethod
    def build_simulated_runtime(
        config: RuntimeConfig | None = None,
        *,
        slippage_rate: float = 0.0,
        order_id_prefix: str = "sim_order",
        reject_next_order: bool = False,
        rejected_symbols: Iterable[str] | None = None,
        reject_above_quantity: float | None = None,
        fill_ratio: float = 1.0,
        state: StateEngine | None = None,
        strategy: Strategy | None = None,
        environment: str = "live",
        datastore: DataStore | None = None,
    ) -> Runtime:
        market_data = SimulatedMarketData()
        broker = SimulatedBroker(
            market_data,
            slippage_rate=slippage_rate,
            order_id_prefix=order_id_prefix,
            reject_next_order=reject_next_order,
            rejected_symbols=rejected_symbols,
            reject_above_quantity=reject_above_quantity,
            fill_ratio=fill_ratio,
        )

        return RuntimeFactory.build_runtime(
            config=config,
            market_data=market_data,
            broker=broker,
            state=state,
            strategy=strategy,
            environment=environment,
            datastore=datastore,
        )

    @staticmethod
    def build_sandbox_runtime_from_live(
        live_runtime: Runtime,
        *,
        config: RuntimeConfig | None = None,
        market_data: MarketDataAdapter | None = None,
        broker: BrokerAdapter | None = None,
        strategy: Strategy | None = None,
        datastore: DataStore | None = None,
    ) -> Runtime:
        sandbox_market_data = market_data or SimulatedMarketData()
        sandbox_broker = broker or SimulatedBroker(sandbox_market_data)
        sandbox_state = clone_state_engine(live_runtime.state)

        return RuntimeFactory.build_runtime(
            config=config or live_runtime.config,
            market_data=sandbox_market_data,
            broker=sandbox_broker,
            state=sandbox_state,
            strategy=strategy or deepcopy(live_runtime.strategy),
            environment="sandbox",
            datastore=datastore,
        )
