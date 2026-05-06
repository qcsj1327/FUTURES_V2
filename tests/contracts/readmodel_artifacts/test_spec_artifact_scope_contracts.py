from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.orchestration.spec_artifacts import (
    validate_specs_snapshot_scope,
    write_specs_snapshot,
)
from core.instruments.specs import InstrumentSpec, InstrumentSpecRegistry


def _specs() -> dict[str, InstrumentSpec]:
    return InstrumentSpecRegistry().specs_for(["au"])


def test_spec_artifact_contains_scope_metadata(tmp_path: Path) -> None:
    path = write_specs_snapshot(
        runtime_id="rt_specs",
        runtime_profile="live",
        datastore_scope="live",
        specs=_specs(),
        output_dir=tmp_path / "live" / "specs",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "1"
    assert payload["artifact_type"] == "instrument_specs"
    assert payload["runtime_id"] == "rt_specs"
    assert payload["runtime_profile"] == "live"
    assert payload["datastore_scope"] == "live"
    assert payload["is_live"] is True
    assert payload["generated_at"]


def test_spec_artifact_scope_paths_do_not_mix(tmp_path: Path) -> None:
    local = write_specs_snapshot(
        runtime_id="rt_specs",
        runtime_profile="local",
        datastore_scope="local",
        specs=_specs(),
        output_dir=tmp_path / "local" / "specs",
    )
    live = write_specs_snapshot(
        runtime_id="rt_specs",
        runtime_profile="live",
        datastore_scope="live",
        specs=_specs(),
        output_dir=tmp_path / "live" / "specs",
    )

    assert "/local/specs/" in local.as_posix()
    assert "/live/specs/" in live.as_posix()
    assert json.loads(local.read_text(encoding="utf-8"))["is_live"] is False
    assert json.loads(live.read_text(encoding="utf-8"))["is_live"] is True


def test_legacy_spec_artifact_missing_scope_cannot_be_used_as_live(
    tmp_path: Path,
) -> None:
    path = tmp_path / "specs_legacy.json"
    path.write_text(
        json.dumps({"runtime_id": "rt_specs", "specs": {"au": {}}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="runtime_profile mismatch"):
        validate_specs_snapshot_scope(
            path=path,
            expected_runtime_profile="live",
            expected_datastore_scope="live",
        )


def test_spec_artifact_scope_validation_rejects_mismatch(tmp_path: Path) -> None:
    path = write_specs_snapshot(
        runtime_id="rt_specs",
        runtime_profile="dryrun",
        datastore_scope="dryrun",
        specs=_specs(),
        output_dir=tmp_path / "dryrun" / "specs",
    )

    with pytest.raises(ValueError, match="datastore_scope mismatch"):
        validate_specs_snapshot_scope(
            path=path,
            expected_runtime_profile="dryrun",
            expected_datastore_scope="live",
        )
