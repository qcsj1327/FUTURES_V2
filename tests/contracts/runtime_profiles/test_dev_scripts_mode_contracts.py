from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def run_script(
    script: str,
    env: dict[str, str],
    *,
    user_input: str | None = None,
) -> subprocess.CompletedProcess[str]:
    merged = {**os.environ, **env}
    return subprocess.run(
        ["bash", script],
        cwd=ROOT,
        env=merged,
        input=user_input,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )


def test_dev_up_interactive_mode_menu_is_visible() -> None:
    result = run_script(
        "scripts/dev_up.sh",
        {},
        user_input="\n",
    )
    assert result.returncode == 1
    assert "1) local" in result.stderr
    assert "2) dryrun" in result.stderr
    assert "3) live" in result.stderr


def test_dev_up_local_mode_shows_writer_enabled_without_starting() -> None:
    result = run_script(
        "scripts/dev_up.sh",
        {
            "DEV_START_MODE": "local",
            "DEV_NONINTERACTIVE": "1",
            "DEV_AUTO_CONFIRM": "0",
            "DEV_RUNTIME_ID": "rt_script_contract",
        },
    )
    assert result.returncode == 1
    assert "mode: local" in result.stdout
    assert "local_quote_writer: enabled" in result.stdout
    assert "confirmation required" in result.stderr


def test_dev_up_local_mode_writes_seed_quote_before_starting_services(tmp_path: Path) -> None:
    prices = ROOT / "plans" / "prices.json"
    backup = prices.read_text(encoding="utf-8") if prices.exists() else None
    if prices.exists():
        prices.unlink()
    try:
        result = run_script(
            "scripts/dev_up.sh",
            {
                "DEV_START_MODE": "local",
                "DEV_NONINTERACTIVE": "1",
                "DEV_AUTO_CONFIRM": "1",
                "DEV_RUNTIME_ID": "rt_seed_quote_contract",
                "PYTHON": str(ROOT / ".venv" / "bin" / "python"),
                "WEB_PORT": "65534",
            },
        )
        assert prices.exists()
        assert "mode: local" in result.stdout
    finally:
        run_script(
            "scripts/dev_down.sh",
            {
                "DEV_DOWN_SKIP_SWEEP": "1",
                "DEV_DOWN_SKIP_PORT_CLEANUP": "1",
            },
        )
        if backup is None:
            prices.unlink(missing_ok=True)
        else:
            prices.write_text(backup, encoding="utf-8")


def test_dev_up_dryrun_does_not_enable_writer() -> None:
    result = run_script(
        "scripts/dev_up.sh",
        {
            "DEV_START_MODE": "dryrun",
            "DEV_NONINTERACTIVE": "1",
            "DEV_AUTO_CONFIRM": "0",
            "DEV_RUNTIME_ID": "rt_script_contract",
        },
    )
    assert result.returncode == 1
    assert "mode: dryrun" in result.stdout
    assert "local_quote_writer: disabled" in result.stdout
    assert "confirmation required" in result.stderr


def test_dev_up_live_requires_runtime_token() -> None:
    result = run_script(
        "scripts/dev_up.sh",
        {
            "DEV_START_MODE": "live",
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
            "DEV_START_MODE": "unsupported",
            "DEV_NONINTERACTIVE": "1",
            "DEV_AUTO_CONFIRM": "1",
        },
    )
    assert result.returncode == 1
    assert "unsupported DEV_START_MODE=unsupported" in result.stderr
