#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python}"

"$PYTHON" -m ruff check .
"$PYTHON" -m compileall -q .
"$PYTHON" -m mypy .
"$PYTHON" -m pytest -q
