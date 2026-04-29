from __future__ import annotations

from collections.abc import Iterable

from app.runtime import Runtime
from app.runtime_config import RuntimeConfig


class RuntimeRegistry:
    def __init__(self) -> None:
        self._runtimes: dict[str, Runtime] = {}

    def register(self, runtime: Runtime) -> None:
        runtime_id = runtime.config.runtime_id
        self._runtimes[runtime_id] = runtime

    def build_from_configs(self, configs: Iterable[RuntimeConfig]) -> None:
        for cfg in configs:
            self.register(Runtime(cfg))

    def get(self, runtime_id: str) -> Runtime:
        return self._runtimes[runtime_id]

    def all(self) -> list[Runtime]:
        return list(self._runtimes.values())
