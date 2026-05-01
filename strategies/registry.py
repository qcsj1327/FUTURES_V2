from __future__ import annotations

from collections.abc import Callable
from typing import Any

from strategies.base.simple_strategy import StrategyEngine
from strategies.base.strategy import Strategy
from strategies.parametrized_strategy import ParametrizedStrategy


class StrategyRegistry:
    """
    Backward-compatible instance registry used by orchestrator/strategy_runner/tests.
    Also provides a strict factory for configured strategies (no silent fallback).
    """

    # known base strategy builders (strict)
    _builders: dict[str, Callable[[], Strategy]] = {
        "simple_strategy": lambda: StrategyEngine(),
        "simple_strategy_alt": lambda: StrategyEngine(),
    }

    def __init__(self) -> None:
        self._items: dict[str, Strategy] = {}

    def register(self, name: str, strategy: Strategy) -> None:
        self._items[name] = strategy

    def all(self) -> dict[str, Strategy]:
        return dict(self._items)

    def get(self, name: str) -> Strategy:
        return self._items[name]

    @classmethod
    def names(cls) -> list[str]:
        return sorted(cls._builders.keys())

    @classmethod
    def build_base(cls, name: str) -> Strategy:
        if name not in cls._builders:
            raise ValueError(f"unknown strategy: {name}")
        return cls._builders[name]()

    @classmethod
    def create(cls, *, name: str, params: dict[str, Any]) -> Strategy:
        base = cls.build_base(name)
        return ParametrizedStrategy(strategy_name=name, base=base, params=params)


def create_strategy(*, name: str, params: dict[str, Any]) -> Strategy:
    return StrategyRegistry.create(name=name, params=params)
