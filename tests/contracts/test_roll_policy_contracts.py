from __future__ import annotations

from pathlib import Path

from adapters.storage.datastore_fs import JSONLFileDataStore
from core.instruments.roll_policy import RollPolicy


def test_fixed_contract_policy_never_rolls(tmp_path: Path) -> None:
    store = JSONLFileDataStore(root_dir=tmp_path / "live", env="live", runtime_id="rt_roll")
    policy = RollPolicy(
        mode="fixed_contract",
        contracts={"au": "SHFE.au2406"},
        runtime_id="rt_roll",
        env="live",
        sink=store,
    )

    assert policy.resolve("au", 1) == "SHFE.au2406"
    policy.contracts["au"] = "SHFE.au2407"
    assert policy.resolve("au_main", 2) == "SHFE.au2406"
    assert store.read_roll_events(env="live") == []


def test_fixed_main_policy_writes_roll_event(tmp_path: Path) -> None:
    store = JSONLFileDataStore(root_dir=tmp_path / "live", env="live", runtime_id="rt_roll")
    policy = RollPolicy(
        mode="fixed_main",
        contracts={"au": "SHFE.au2406"},
        runtime_id="rt_roll",
        env="live",
        sink=store,
    )

    assert policy.resolve("au", 1) == "SHFE.au2406"
    policy.contracts["au"] = "SHFE.au2407"
    assert policy.resolve("au_main", 2) == "SHFE.au2407"

    events = store.read_roll_events(env="live")
    assert len(events) == 1
    assert events[0] == {
        "event_type": "roll",
        "runtime_id": "rt_roll",
        "base_symbol": "au",
        "from_contract": "SHFE.au2406",
        "to_contract": "SHFE.au2407",
        "ts": 2,
        "reason": "fixed_main_contract_changed",
    }
