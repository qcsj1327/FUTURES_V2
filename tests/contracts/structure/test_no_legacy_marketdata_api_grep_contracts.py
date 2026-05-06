from __future__ import annotations

import subprocess


def test_repo_has_no_legacy_marketdata_api_names() -> None:
    # Keep this strict: no legacy names in code/tests/docs.
    legacy_1 = "get_last_" + "price"
    legacy_2 = "get_last_" + "prices"
    pattern = f"{legacy_1}|{legacy_2}"
    cmd = ["rg", "-n", pattern, "-S", "."]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode == 1, res.stdout
