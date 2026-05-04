#!/usr/bin/env bash
set -euo pipefail

RUNTIME_ID="${RUNTIME_ID:-rt_livefile}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
SMOKE_SECONDS="${SMOKE_SECONDS:-180}"
KEEP_UP="${KEEP_UP:-0}"

before="$(mktemp)"
after="$(mktemp)"

cleanup() {
  rm -f "$before" "$after"
  if [[ "$KEEP_UP" != "1" ]]; then
    scripts/dev_down.sh >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

scripts/dev_down.sh >/dev/null 2>&1 || true
scripts/dev_up.sh

sleep 3
python -m tools.inspect_run "$RUNTIME_ID" --tail 1 > "$before" || true

sleep "$SMOKE_SECONDS"

python -m tools.inspect_run "$RUNTIME_ID" --tail 5 > "$after"
curl -fsS "$BASE_URL/runs/$RUNTIME_ID" >/dev/null
curl -fsS "$BASE_URL/runs/$RUNTIME_ID/events?env=live&tail=20" >/dev/null

python - "$before" "$after" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


def read(path: str) -> dict[str, object]:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def live_stats(report: dict[str, object]) -> dict[str, int]:
    stores = report.get("stores")
    if not isinstance(stores, dict):
        return {}
    live = stores.get("live")
    if not isinstance(live, dict):
        return {}
    stats = live.get("stats")
    if not isinstance(stats, dict):
        return {}
    return {k: int(v) for k, v in stats.items() if isinstance(v, int)}


before = live_stats(read(sys.argv[1]))
after = live_stats(read(sys.argv[2]))
print("long_run_smoke stats:")
for key in sorted(set(before) | set(after)):
    print(f"  {key}: {before.get(key, 0)} -> {after.get(key, 0)}")

if after.get("portfolio_snapshots_lines", 0) <= before.get("portfolio_snapshots_lines", 0):
    raise SystemExit("portfolio_snapshots_lines did not grow")
PY

echo "OK: $RUNTIME_ID smoke passed"
