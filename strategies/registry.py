from __future__ import annotations

from collections.abc import Callable
from typing import Any

from strategies.base.simple_strategy import StrategyEngine
from strategies.base.strategy import Strategy
from strategies.parametrized_strategy import ParametrizedStrategy
from strategies.volume.volume_ma_reversion import VolumeMAReversion
from strategies.volume.volume_observer_guard import VolumeObserverGuard
from strategies.volume.volume_spike_breakout import VolumeSpikeBreakout
from strategies.volume.volume_trend_filter import VolumeTrendFilter


class StrategyRegistry:
    """
    Backward-compatible instance registry used by orchestrator/strategy_runner/tests.
    Also provides a strict factory for configured strategies (no silent fallback).
    """

    _builders: dict[str, Callable[[dict[str, Any]], Strategy]] = {
        "simple_strategy": lambda _params: StrategyEngine(),
        "simple_strategy_alt": lambda _params: StrategyEngine(),
        "volume_spike_breakout": VolumeSpikeBreakout.from_params,
        "volume_ma_reversion": VolumeMAReversion.from_params,
        "volume_trend_filter": VolumeTrendFilter.from_params,
        "volume_observer_guard": VolumeObserverGuard.from_params,
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
    def build_base(cls, name: str, params: dict[str, Any] | None = None) -> Strategy:
        if name not in cls._builders:
            raise ValueError(f"unknown strategy: {name}")
        return cls._builders[name](dict(params or {}))

    @classmethod
    def create(cls, *, name: str, params: dict[str, Any]) -> Strategy:
        base = cls.build_base(name, params=params)
        return ParametrizedStrategy(strategy_name=name, base=base, params=params)


def create_strategy(*, name: str, params: dict[str, Any]) -> Strategy:
    return StrategyRegistry.create(name=name, params=params)
