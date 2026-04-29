from __future__ import annotations

from collections.abc import Mapping

from strategies.base.strategy import Strategy


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, Strategy] = {}

    def register(self, name: str, strategy: Strategy) -> None:
        self._strategies[name] = strategy

    def get(self, name: str) -> Strategy:
        return self._strategies[name]

    def all(self) -> Mapping[str, Strategy]:
        return self._strategies
