from __future__ import annotations

from dataclasses import replace

from adapters.broker.base import BrokerAdapter
from adapters.marketdata.base import MarketDataAdapter
from app.runtime_config import RuntimeConfig
from core.execution.execution_engine import ExecutionEngine
from core.instruments.calendar import TradingCalendar
from core.instruments.resolver import InstrumentResolver
from core.instruments.roll_policy import RollPolicy
from core.portfolio.portfolio_engine import PortfolioEngine
from core.risk.risk_engine import RiskEngine
from core.services.runtime.datastore import DataStore
from core.services.runtime.event_codec import (
    build_base_event,
    encode_execution_event,
    encode_order_event,
)
from core.services.trade.exit_service import ExitService
from core.state.state_engine import StateEngine
from core.trigger.trigger_engine import TriggerEngine
from domain.signal import SignalDecision
from strategies.base.simple_strategy import StrategyEngine
from strategies.base.strategy import Strategy


class Runtime:
    def __init__(
        self,
        config: RuntimeConfig | None = None,
        *,
        market_data: MarketDataAdapter,
        broker: BrokerAdapter,
        state: StateEngine | None = None,
        strategy: Strategy | None = None,
        environment: str = "live",
        datastore: DataStore | None = None,
        runtime_id: str | None = None,
        trading_calendar: TradingCalendar | None = None,
        instrument_resolver: InstrumentResolver | None = None,
    ) -> None:
        self.config = config or RuntimeConfig()
        self.runtime_id = runtime_id or self.config.runtime_id

        self.trigger = TriggerEngine()
        self.portfolio = PortfolioEngine()
        self.risk = RiskEngine()
        self.execution = ExecutionEngine(broker)
        self.state = state or StateEngine(runtime_id=self.runtime_id)
        self.exit_service = ExitService()
        self.strategy = strategy or StrategyEngine()
        self.market_data = market_data
        self.trading_calendar = trading_calendar or TradingCalendar(sessions_by_symbol={})
        default_policy = RollPolicy(
            mode="fixed_contract",
            contracts={
                self.config.symbol: f"{self.config.symbol}_main",
                "au": "au_main",
                "ag": "ag_main",
                "rb": "rb_main",
            },
            runtime_id=self.runtime_id,
            env=environment,
            sink=datastore,
        )
        self.instrument_resolver = instrument_resolver or InstrumentResolver(
            roll_policy=default_policy
        )

        self.environment = environment
        self.datastore = datastore
        self.orders_submitted = 0
        self._tick = 0

    def run_market_once(
        self,
        *,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> None:
        quote = self.market_data.get_last_quote(self.config.symbol)
        quote_ts = quote.ts if quote.ts is not None else self._tick
        if not self.trading_calendar.is_trading_time(self.config.symbol, quote_ts):
            self._maybe_save_snapshot()
            return
        decision = self.strategy.generate(self.config.symbol, quote)
        self.run(decision, market_ts=quote_ts)

        for position in list(self.state.portfolio.positions.values()):
            exit_order = self.exit_service.create_exit_order(
                position=position,
                current_price=quote.price,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
            if exit_order is None:
                continue

            exit_result = self.execution.broker.submit_order(exit_order)
            if exit_result.success:
                self.orders_submitted += 1

            self._maybe_append_events(
                exit_order,
                exit_result,
                strategy_name="exit",
                strategy_impl="ExitService",
            )
            self.state.apply(exit_order, exit_result, strategy_name="exit")
            self._maybe_save_snapshot()

    def run(
        self,
        decision: SignalDecision,
        *,
        strategy_name: str | None = None,
        strategy_impl: str | None = None,
        market_ts: int | None = None,
    ) -> None:
        ts = market_ts if market_ts is not None else decision.ts
        if ts is None:
            ts = self._tick
        base = self._decision_base_symbol(decision)
        if not self.trading_calendar.is_trading_time(base, int(ts)):
            self._maybe_save_snapshot()
            return
        prepared = self._inject_instrument(decision, base_symbol=base, ts=int(ts))
        self._run_decision(prepared, strategy_name=strategy_name, strategy_impl=strategy_impl)

    def _decision_base_symbol(self, decision: SignalDecision) -> str:
        for value in (decision.symbol, decision.instrument_id, decision.trade_instrument_id):
            if isinstance(value, str) and value:
                return self.instrument_resolver.base_symbol(value)
        return self.instrument_resolver.base_symbol(self.config.symbol)

    def _inject_instrument(
        self,
        decision: SignalDecision,
        *,
        base_symbol: str,
        ts: int,
    ) -> SignalDecision:
        trade_id = self.instrument_resolver.resolve_trade_instrument_id(base_symbol, ts)
        return replace(
            decision,
            symbol=base_symbol,
            instrument_id=base_symbol,
            trade_instrument_id=trade_id,
            runtime_id=self.runtime_id,
            ts=decision.ts if decision.ts is not None else ts,
            bar_ts=decision.bar_ts if decision.bar_ts is not None else ts,
        )

    def _run_decision(
        self,
        decision: SignalDecision,
        *,
        strategy_name: str | None = None,
        strategy_impl: str | None = None,
    ) -> None:
        trigger_result = self.trigger.process(
            decision,
            runtime_id=self.runtime_id,
        )
        allocation = self.portfolio.allocate(
            trigger_result,
            default_quantity=self.config.default_quantity,
        )
        risk_decision = self.risk.evaluate(allocation, portfolio=self.state.portfolio)

        order, exec_result = self.execution.execute(risk_decision)
        if order is not None and exec_result.success:
            self.orders_submitted += 1

        name = (
            strategy_name
            or getattr(decision, "strategy_name", None)
            or "main"
        )
        self._maybe_append_events(
            order,
            exec_result,
            strategy_name=name,
            strategy_impl=strategy_impl,
        )
        self.state.apply(order, exec_result)
        self._maybe_save_snapshot()

    def _maybe_append_events(
        self,
        order: object | None,
        exec_result: object,
        *,
        strategy_name: str,
        strategy_impl: str | None = None,
    ) -> None:
        if self.datastore is None:
            return

        base = build_base_event(
            ts=self._tick,
            runtime_id=self.runtime_id,
            env=self.environment,
            strategy_name=strategy_name,
            symbol=self.config.symbol,
            strategy_impl=strategy_impl,
        )

        order_payload = encode_order_event(order)
        if order_payload:
            self.datastore.append_order_event(
                {**base, **order_payload},
                env=self.environment,
            )

        exec_payload = encode_execution_event(exec_result)
        self.datastore.append_fill_event(
            {**base, **exec_payload},
            env=self.environment,
        )

    def _maybe_save_snapshot(self) -> None:
        if self.datastore is None:
            self._tick += 1
            return

        self.datastore.save_portfolio_snapshot(
            ts=self._tick,
            portfolio=self.state.portfolio,
            env=self.environment,
        )
        self._tick += 1
