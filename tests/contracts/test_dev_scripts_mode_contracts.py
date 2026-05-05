from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_script(script: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    merged = {**os.environ, **env}
    return subprocess.run(
        ["bash", script],
        cwd=ROOT,
        env=merged,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )


def test_dev_up_live_file_mode_shows_writer_enabled_without_starting() -> None:
    result = run_script(
        "scripts/dev_up.sh",
        {
            "DEV_START_MODE": "live_file",
            "DEV_NONINTERACTIVE": "1",
            "DEV_AUTO_CONFIRM": "0",
            "DEV_RUNTIME_ID": "rt_script_contract",
        },
    )
    assert result.returncode == 1
    assert "mode: live_file" in result.stdout
    assert "mock_prices_writer: enabled" in result.stdout
    assert "confirmation required" in result.stderr


def test_dev_up_tqkq_dryrun_does_not_enable_writer() -> None:
    result = run_script(
        "scripts/dev_up.sh",
        {
            "DEV_START_MODE": "tqkq_dryrun",
            "DEV_NONINTERACTIVE": "1",
            "DEV_AUTO_CONFIRM": "0",
            "DEV_RUNTIME_ID": "rt_script_contract",
        },
    )
    assert result.returncode == 1
    assert "mode: tqkq_dryrun" in result.stdout
    assert "mock_prices_writer: disabled" in result.stdout
    assert "confirmation required" in result.stderr


def test_dev_up_tqkq_live_submit_requires_runtime_token() -> None:
    result = run_script(
        "scripts/dev_up.sh",
        {
            "DEV_START_MODE": "tqkq_live_submit",
            "DEV_NONINTERACTIVE": "1",
            "DEV_AUTO_CONFIRM": "1",
            "DEV_RUNTIME_ID": "rt_script_contract",
            "DEV_LIVE_CONFIRM_TOKEN": "wrong",
        },
    )
    assert result.returncode == 1
    assert "confirm token equal to runtime_id" in result.stderr


def test_dev_down_handles_missing_and_empty_pid_files() -> None:
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    empty_pid = logs / "script_contract_empty.pid"
    empty_pid.write_text("", encoding="utf-8")
    result = run_script(
        "scripts/dev_down.sh",
        {
            "DEV_DOWN_SKIP_SWEEP": "1",
            "DEV_DOWN_SKIP_PORT_CLEANUP": "1",
        },
    )
    assert result.returncode == 0
    assert "empty pid" in result.stdout
    assert not empty_pid.exists()


def test_long_run_smoke_rejects_unsupported_mode_before_startup() -> None:
    result = run_script(
        "scripts/long_run_smoke.sh",
        {
            "DEV_START_MODE": "tqkq_sim",
            "DEV_NONINTERACTIVE": "1",
            "DEV_AUTO_CONFIRM": "1",
        },
    )
    assert result.returncode == 1
    assert "unsupported DEV_START_MODE=tqkq_sim" in result.stderr
