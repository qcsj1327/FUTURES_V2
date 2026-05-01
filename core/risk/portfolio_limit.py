from __future__ import annotations

from core.portfolio.portfolio_engine import PortfolioAllocation
from domain.enums import Decision
from domain.state import PortfolioState


class PortfolioLimit:
    def __init__(
        self,
        *,
        max_total_exposure: float | None = None,
        max_active_symbols: int | None = None,
        max_symbol_weight: float | None = None,
    ) -> None:
        if max_total_exposure is not None and max_total_exposure < 0:
            raise ValueError("max_total_exposure_must_be_non_negative")

        if max_active_symbols is not None and max_active_symbols < 0:
            raise ValueError("max_active_symbols_must_be_non_negative")

        if max_symbol_weight is not None and not 0 <= max_symbol_weight <= 1:
            raise ValueError("max_symbol_weight_must_be_between_0_and_1")

        self.max_total_exposure = max_total_exposure
        self.max_active_symbols = max_active_symbols
        self.max_symbol_weight = max_symbol_weight

    def check(
        self,
        *,
        allocation: PortfolioAllocation,
        portfolio: PortfolioState | None,
        price: float | None,
    ) -> str | None:
        if allocation.quantity is None:
            return None

        if not self._is_open_trade(allocation):
            return None

        if self._exceeds_max_active_symbols(allocation, portfolio):
            return "max_active_symbols_exceeded"

        if self._exceeds_max_total_exposure(
            allocation=allocation,
            portfolio=portfolio,
            price=price,
        ):
            return "max_total_exposure_exceeded"

        symbol_weight_reason = self._symbol_weight_reason(
            allocation=allocation,
            portfolio=portfolio,
            price=price,
        )
        if symbol_weight_reason is not None:
            return symbol_weight_reason

        return None

    def _exceeds_max_total_exposure(
        self,
        *,
        allocation: PortfolioAllocation,
        portfolio: PortfolioState | None,
        price: float | None,
    ) -> bool:
        if self.max_total_exposure is None:
            return False

        if allocation.quantity is None:
            return False

        if price is None:
            return False

        current_exposure = self._current_exposure(portfolio)
        next_exposure = allocation.quantity * price

        return current_exposure + next_exposure > self.max_total_exposure

    def _exceeds_max_active_symbols(
        self,
        allocation: PortfolioAllocation,
        portfolio: PortfolioState | None,
    ) -> bool:
        if self.max_active_symbols is None:
            return False

        trigger = allocation.trigger

        if portfolio is None or trigger.instrument_id is None:
            return False

        active_symbols = {
            position.instrument_id
            for position in portfolio.positions.values()
            if position.quantity > 0
        }

        if trigger.instrument_id in active_symbols:
            return False

        return len(active_symbols) + 1 > self.max_active_symbols

    def _symbol_weight_reason(
        self,
        *,
        allocation: PortfolioAllocation,
        portfolio: PortfolioState | None,
        price: float | None,
    ) -> str | None:
        if self.max_symbol_weight is None:
            return None

        if allocation.quantity is None:
            return None

        if price is None:
            return None

        if portfolio is None or portfolio.equity is None or portfolio.equity <= 0:
            return "portfolio_equity_required"

        trigger = allocation.trigger
        if trigger.instrument_id is None:
            return None

        current_symbol_exposure = self._current_symbol_exposure(
            portfolio=portfolio,
            instrument_id=trigger.instrument_id,
        )
        next_exposure = allocation.quantity * price
        next_weight = (current_symbol_exposure + next_exposure) / portfolio.equity

        if next_weight > self.max_symbol_weight:
            return "max_symbol_weight_exceeded"

        return None

    def _current_exposure(self, portfolio: PortfolioState | None) -> float:
        if portfolio is None:
            return 0.0

        exposure = 0.0

        for position in portfolio.positions.values():
            if position.quantity <= 0:
                continue

            if position.avg_price is None:
                continue

            exposure += position.quantity * position.avg_price

        return exposure

    def _current_symbol_exposure(
        self,
        *,
        portfolio: PortfolioState,
        instrument_id: str,
    ) -> float:
        exposure = 0.0

        for position in portfolio.positions.values():
            if position.instrument_id != instrument_id:
                continue

            if position.quantity <= 0:
                continue

            if position.avg_price is None:
                continue

            exposure += position.quantity * position.avg_price

        return exposure

    def _is_open_trade(self, allocation: PortfolioAllocation) -> bool:
        return allocation.trigger.decision in {
            Decision.OPEN_LONG,
            Decision.OPEN_SHORT,
        }
