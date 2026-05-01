from __future__ import annotations

from app.runtime_config import RuntimeConfig
from app.runtime_registry import RuntimeRegistry


def test_runtime_registry_build_and_get() -> None:
    registry = RuntimeRegistry()

    configs = [
        RuntimeConfig(runtime_id="r1", default_quantity=1.0),
        RuntimeConfig(runtime_id="r2", default_quantity=2.0),
    ]

    registry.build_from_configs(configs)

    r1 = registry.get("r1")
    r2 = registry.get("r2")

    assert r1.config.runtime_id == "r1"
    assert r2.config.runtime_id == "r2"
    assert r1.config.default_quantity == 1.0
    assert r2.config.default_quantity == 2.0


def test_runtime_registry_all() -> None:
    registry = RuntimeRegistry()

    configs = [
        RuntimeConfig(runtime_id="a"),
        RuntimeConfig(runtime_id="b"),
    ]

    registry.build_from_configs(configs)

    runtimes = registry.all()

    assert len(runtimes) == 2
    assert {r.config.runtime_id for r in runtimes} == {"a", "b"}
