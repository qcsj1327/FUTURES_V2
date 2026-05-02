from __future__ import annotations

import importlib.util


def test_dev_deps_httpx_present() -> None:
    assert importlib.util.find_spec("httpx") is not None, (
        "Missing dependency: httpx. "
        "Install dev deps with: pip install -r requirements-dev.txt"
    )
