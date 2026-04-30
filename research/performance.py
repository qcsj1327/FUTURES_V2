from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


@dataclass(frozen=True)
class PerformanceMetrics:
    total_return: float
    max_drawdown: float
    volatility: float
    sharpe_ratio: float | None


class PerformanceAnalyzer:
    def analyze(self, equity_curve: list[float]) -> PerformanceMetrics:
        if not equity_curve:
            return PerformanceMetrics(
                total_return=0.0,
                max_drawdown=0.0,
                volatility=0.0,
                sharpe_ratio=None,
            )

        total_return = self._total_return(equity_curve)
        returns = self._returns(equity_curve)
        volatility = self._volatility(returns)
        sharpe_ratio = self._sharpe_ratio(returns, volatility)

        return PerformanceMetrics(
            total_return=total_return,
            max_drawdown=self._max_drawdown(equity_curve),
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
        )

    def _total_return(self, equity_curve: list[float]) -> float:
        first = equity_curve[0]
        last = equity_curve[-1]

        if first == 0:
            return 0.0

        return (last - first) / first

    def _returns(self, equity_curve: list[float]) -> list[float]:
        returns: list[float] = []

        for previous, current in zip(equity_curve, equity_curve[1:], strict=False):
            if previous == 0:
                returns.append(0.0)
            else:
                returns.append((current - previous) / previous)

        return returns

    def _volatility(self, returns: list[float]) -> float:
        if len(returns) < 2:
            return 0.0

        mean = sum(returns) / len(returns)
        variance = sum((value - mean) ** 2 for value in returns) / len(returns)

        return sqrt(variance)

    def _sharpe_ratio(
        self,
        returns: list[float],
        volatility: float,
    ) -> float | None:
        if not returns or volatility == 0:
            return None

        mean = sum(returns) / len(returns)

        return mean / volatility

    def _max_drawdown(self, equity_curve: list[float]) -> float:
        if not equity_curve:
            return 0.0

        peak = equity_curve[0]
        max_drawdown = 0.0

        for equity in equity_curve:
            peak = max(peak, equity)

            if peak == 0:
                continue

            drawdown = (peak - equity) / peak
            max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown
