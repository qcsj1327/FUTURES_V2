from __future__ import annotations

from pathlib import Path

import pytest

from adapters.storage.datastore_fs import JSONLFileDataStore
from adapters.storage.datastore_memory import MemoryDataStore
from core.services.runtime.datastore import EnvironmentMismatchError


def test_memory_store_env_mismatch_raises() -> None:
    s = MemoryDataStore(env="live", runtime_id="r1")
    with pytest.raises(EnvironmentMismatchError):
        s.append_order_event({"x": 1}, env="sandbox")


def test_fs_store_writes_are_isolated_by_env(tmp_path: Path) -> None:
    live = JSONLFileDataStore(root_dir=tmp_path, env="live", runtime_id="r1")
    sandbox = JSONLFileDataStore(root_dir=tmp_path, env="sandbox", runtime_id="r1")

    live.append_order_event({"id": "o1"}, env="live")
    sandbox.append_order_event({"id": "o2"}, env="sandbox")

    live_path = tmp_path / "live" / "r1" / "order_events.jsonl"
    sandbox_path = tmp_path / "sandbox" / "r1" / "order_events.jsonl"

    assert live_path.exists()
    assert sandbox_path.exists()

    assert "o1" in live_path.read_text(encoding="utf-8")
    assert "o2" not in live_path.read_text(encoding="utf-8")

    assert "o2" in sandbox_path.read_text(encoding="utf-8")
    assert "o1" not in sandbox_path.read_text(encoding="utf-8")
