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


def _load(
    root: Path,
    *,
    runtime_id: str = "rt_same",
    profile: str = "live",
    scope: str = "live",
    diagnostics: list[str] | None = None,
) -> dict[str, list[str]] | None:
    return load_approved_strategy_map(
        runtime_id=runtime_id,
        artifacts_root=root,
        expected_runtime_profile=profile,
        expected_datastore_scope=scope,
        diagnostics=diagnostics,
    )


def test_live_session_does_not_load_local_approved_artifact(tmp_path: Path) -> None:
    write_strategy_switch_approved(
        proposal=_proposal("rt_same", "local"),
        output_path=approved_path(
            runtime_id="rt_same",
            artifacts_root=tmp_path,
            scope="local",
        ),
    )

    assert _load(tmp_path) is None


def test_live_session_rejects_legacy_local_artifact_with_same_runtime_id(
    tmp_path: Path,
) -> None:
    diagnostics: list[str] = []
    legacy_path = tmp_path / "strategy_switch" / "strategy_switch_approved_rt_same.json"
    write_strategy_switch_approved(
        proposal=_proposal("rt_same", "local"),
        output_path=legacy_path,
    )

    assert _load(tmp_path, diagnostics=diagnostics) is None
    assert any("approved_not_found" in item for item in diagnostics)


def test_live_session_rejects_dryrun_artifact_with_same_runtime_id(tmp_path: Path) -> None:
    diagnostics: list[str] = []
    legacy_path = tmp_path / "strategy_switch" / "strategy_switch_approved_rt_same.json"
    write_strategy_switch_approved(
        proposal=_proposal("rt_same", "dryrun"),
        output_path=legacy_path,
    )

    assert _load(tmp_path, diagnostics=diagnostics) is None
    assert any("approved_not_found" in item for item in diagnostics)


def test_legacy_artifact_missing_scope_is_not_loaded_by_live(tmp_path: Path) -> None:
    path = tmp_path / "strategy_switch" / "strategy_switch_approved_rt_same.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "kind": "strategy_switch_approved",
                "runtime_id": "rt_same",
                "enabled_strategies_by_symbol": {"au": ["legacy_strategy"]},
            }
        ),
        encoding="utf-8",
    )

    diagnostics: list[str] = []

    assert _load(tmp_path, diagnostics=diagnostics) is None
    assert any("approved_not_found" in item for item in diagnostics)


def test_scope_matching_approved_artifact_loads(tmp_path: Path) -> None:
    write_strategy_switch_approved(
        proposal=_proposal("rt_same", "live"),
        output_path=approved_path(
            runtime_id="rt_same",
            artifacts_root=tmp_path,
            scope="live",
        ),
    )

    assert _load(tmp_path) == {"au": ["simple_strategy"]}
