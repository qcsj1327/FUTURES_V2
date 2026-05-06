from __future__ import annotations

from collections.abc import Iterable

from app.runtime import Runtime
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory


class RuntimeRegistry:
    def __init__(self) -> None:
        self._runtimes: dict[str, Runtime] = {}

    def register(self, runtime: Runtime) -> None:
        self._runtimes[runtime.config.runtime_id] = runtime

    def get(self, runtime_id: str) -> Runtime:
        return self._runtimes[runtime_id]

    def all(self) -> tuple[Runtime, ...]:
        return tuple(self._runtimes.values())

    def build_from_configs(self, configs: Iterable[RuntimeConfig]) -> None:
        for cfg in configs:
            self.register(RuntimeFactory.build_local_runtime(cfg))
