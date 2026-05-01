from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class DataStoreError(Exception):
    """Base error for datastore operations."""


class EnvironmentMismatchError(DataStoreError):
    """Raised when a write targets a store for a different environment."""


class InvalidWriteError(DataStoreError):
    """Raised when a write is semantically invalid (e.g., non-append-only)."""


class DataStore(ABC):
    """
    Runtime side-effect sink. Must be environment-isolated.

    NOTE:
    - env is a simple string for now ("live", "sandbox", "paper", "dev").
      Later you can wire it to your existing runtime env definition (no need to add a new enum now).
    - All writes are append-only by contract.
    """

    def __init__(self, *, env: str, runtime_id: str) -> None:
        self.env = env
        self.runtime_id = runtime_id

    def _assert_env(self, env: str) -> None:
        if env != self.env:
            raise EnvironmentMismatchError(f"write env={env} does not match store env={self.env}")

    @abstractmethod
    def append_order_event(self, event: dict[str, Any], *, env: str) -> None: ...

    @abstractmethod
    def append_fill_event(self, event: dict[str, Any], *, env: str) -> None: ...

    @abstractmethod
    def save_portfolio_snapshot(self, *, ts: int, portfolio: Any, env: str) -> None: ...

    @abstractmethod
    def load_latest_portfolio_snapshot(self, *, env: str) -> Any | None: ...

    @abstractmethod
    def append_metrics(self, *, ts: int, metrics: Mapping[str, Any], env: str) -> None: ...

    @abstractmethod
    def read_order_events(self, *, env: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def read_fill_events(self, *, env: str) -> list[dict[str, Any]]: ...
