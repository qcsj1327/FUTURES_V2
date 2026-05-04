from __future__ import annotations

from pathlib import Path


def test_main_health_runbook_documents_local_loop_and_event_growth() -> None:
    doc = Path("docs/runbook/main_health.md")
    text = doc.read_text(encoding="utf-8")

    required = [
        "scripts/dev_up.sh",
        "scripts/dev_down.sh",
        "logs/web.log",
        "logs/daemon.log",
        "lsof -nP -iTCP:8000 -sTCP:LISTEN",
        "python -m tools.inspect_run rt_livefile",
        "curl -fsS http://127.0.0.1:8000/runs/rt_livefile",
        "order_lifecycle_events.jsonl",
        "rank_events.jsonl",
        "roll_events.jsonl",
        "warnings",
    ]
    for needle in required:
        assert needle in text


def test_long_run_smoke_script_has_required_observability_checks() -> None:
    script = Path("scripts/long_run_smoke.sh")
    text = script.read_text(encoding="utf-8")

    required = [
        "scripts/dev_up.sh",
        "scripts/dev_down.sh",
        "python -m tools.inspect_run",
        "curl -fsS",
        "portfolio_snapshots_lines",
        "SMOKE_SECONDS",
        "rt_livefile",
    ]
    for needle in required:
        assert needle in text

    assert script.stat().st_mode & 0o111
