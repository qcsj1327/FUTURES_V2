from __future__ import annotations

import json
from pathlib import Path

from app.orchestration.strategy_switch import (
    approved_path,
    load_approved_strategy_map,
    write_strategy_switch_approved,
)


def _proposal(runtime_id: str, scope: str) -> dict[str, object]:
    return {
        "kind": "strategy_switch_proposal",
        "schema_version": 1,
        "runtime_id": runtime_id,
        "runtime_profile": scope,
        "datastore_scope": scope,
        "is_live": scope == "live",
        "path": f"strategy_switch_proposal_{runtime_id}.json",
        "enabled_strategies_by_symbol": {"au": ["simple_strategy"]},
    }


def _load(root: Path) -> dict[str, list[str]] | None:
    return load_approved_strategy_map(
        runtime_id="rt_same",
        artifacts_root=root,
        expected_runtime_profile="live",
        expected_datastore_scope="live",
    )


def test_scoped_missing_unscoped_exists_does_not_load(tmp_path: Path) -> None:
    unscoped = tmp_path / "strategy_switch" / "strategy_switch_approved_rt_same.json"
    write_strategy_switch_approved(proposal=_proposal("rt_same", "live"), output_path=unscoped)

    assert _load(tmp_path) is None


def test_unscoped_payload_scope_matching_still_does_not_load(tmp_path: Path) -> None:
    unscoped = tmp_path / "strategy_switch" / "strategy_switch_approved_rt_same.json"
    unscoped.parent.mkdir(parents=True)
    unscoped.write_text(
        json.dumps(
            {
                "kind": "strategy_switch_approved",
                "runtime_id": "rt_same",
                "runtime_profile": "live",
                "datastore_scope": "live",
                "is_live": True,
                "enabled_strategies_by_symbol": {"au": ["legacy"]},
            }
        ),
        encoding="utf-8",
    )

    assert _load(tmp_path) is None


def test_scoped_matching_loads(tmp_path: Path) -> None:
    write_strategy_switch_approved(
        proposal=_proposal("rt_same", "live"),
        output_path=approved_path(runtime_id="rt_same", artifacts_root=tmp_path, scope="live"),
    )

    assert _load(tmp_path) == {"au": ["simple_strategy"]}


def test_approved_path_requires_scope(tmp_path: Path) -> None:
    try:
        approved_path(runtime_id="rt_same", artifacts_root=tmp_path)
    except ValueError as exc:
        assert "explicit scope" in str(exc)
    else:
        raise AssertionError("approved_path without scope must fail")
