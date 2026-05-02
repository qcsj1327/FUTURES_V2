from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_validate_plan_prints_resolved_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    repo_root = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root)

    proc = subprocess.run(
        [sys.executable, "-m", "tools.validate_plan", "--runtime-id", "rt_print",],
        check=True,
        capture_output=True,
        text=True,
            cwd=repo_root,
            env=env,
    )
    data = json.loads(proc.stdout)
    assert data["runtime_id"] == "rt_print"
    assert "datastore" in data
    assert "router" in data
