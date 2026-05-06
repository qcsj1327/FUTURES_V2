from __future__ import annotations

from pathlib import Path

from web.readmodel.dashboard import inspect_run

OLD_TOKENS = (
    "rt_" + "livefile",
    "rt_" + "tqkq" + "_" + "dryrun",
    "live" + "_" + "file",
    "tqkq" + "_" + "dryrun",
    "sand" + "box",
)


def test_current_store_and_artifacts_do_not_contain_legacy_runtime_data() -> None:
    checked_roots = [
        Path("data/store"),
        Path("data/artifacts"),
    ]
    offenders: list[str] = []
    for root in checked_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            rel = str(path)
            if "data/quarantine/" in rel:
                continue
            if any(token in rel for token in OLD_TOKENS):
                offenders.append(rel)
    assert offenders == []


def test_quarantine_is_not_read_by_default(tmp_path: Path) -> None:
    q = tmp_path / "data" / "quarantine" / "legacy_20260508_000000"
    legacy_store = q / "data" / "store" / "live" / ("rt_" + "livefile")
    legacy_store.mkdir(parents=True)
    (legacy_store / "order_events.jsonl").write_text('{"order_id":"legacy"}\n', encoding="utf-8")

    report = inspect_run(
        runtime_id="rt_" + "livefile",
        store_root=tmp_path / "data" / "store",
        artifacts_root=tmp_path / "data" / "artifacts",
    )

    assert report["fail_closed"] is True
    assert report["event_stats"]["live"]["order_events_lines"] == 0
