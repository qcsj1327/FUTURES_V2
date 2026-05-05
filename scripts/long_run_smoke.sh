#!/usr/bin/env bash
set -euo pipefail

MODE="${DEV_START_MODE:-live_file}"
RUNTIME_ID="${DEV_RUNTIME_ID:-}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
SMOKE_SECONDS="${SMOKE_SECONDS:-180}"
KEEP_UP="${KEEP_UP:-0}"
PYTHON_BIN="${PYTHON:-python}"

default_runtime_id() {
  case "$1" in
    live_file) echo "rt_livefile" ;;
    tqkq_dryrun) echo "rt_tqkq_dryrun" ;;
    tqkq_live_submit) echo "rt_tqkq_live_submit" ;;
    *) echo "unsupported DEV_START_MODE=$1" >&2; return 1 ;;
  esac
}

RUNTIME_ID="${RUNTIME_ID:-$(default_runtime_id "$MODE")}"

before="$(mktemp)"
after="$(mktemp)"

cleanup() {
  rm -f "$before" "$after"
  if [[ "$KEEP_UP" != "1" ]]; then
    scripts/dev_down.sh >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "long_run_smoke startup summary"
echo "  mode: $MODE"
echo "  runtime_id: $RUNTIME_ID"
echo "  seconds: $SMOKE_SECONDS"
echo "  keep_up: $KEEP_UP"

if [[ "${DEV_AUTO_CONFIRM:-0}" != "1" && "${DEV_NONINTERACTIVE:-0}" != "1" ]]; then
  read -r -p "Start smoke run? [y/N]: " answer
  [[ "$answer" == "y" || "$answer" == "Y" ]] || exit 1
fi

scripts/dev_down.sh >/dev/null 2>&1 || true
DEV_START_MODE="$MODE" \
DEV_RUNTIME_ID="$RUNTIME_ID" \
DEV_AUTO_CONFIRM="${DEV_AUTO_CONFIRM:-1}" \
DEV_NONINTERACTIVE="${DEV_NONINTERACTIVE:-1}" \
bash scripts/dev_up.sh

sleep 3
"$PYTHON_BIN" -m tools.inspect_run "$RUNTIME_ID" --tail 1 > "$before" || true

sleep "$SMOKE_SECONDS"

"$PYTHON_BIN" -m tools.inspect_run "$RUNTIME_ID" --tail 5 > "$after"
curl -fsS "$BASE_URL/runs/$RUNTIME_ID" >/dev/null
curl -fsS "$BASE_URL/runs/$RUNTIME_ID/events?env=live&tail=20" >/dev/null

"$PYTHON_BIN" - "$before" "$after" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

LIVENESS_KEYS = {
    "portfolio_snapshots_lines",
    "order_lifecycle_events_lines",
    "strategy_score_events_lines",
}


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
for key in sorted(set(before) | set(after) | LIVENESS_KEYS):
    print(f"  {key}: {before.get(key, 0)} -> {after.get(key, 0)}")

if not any(after.get(key, 0) > before.get(key, 0) for key in LIVENESS_KEYS):
    raise SystemExit(
        "no liveness metric grew: "
        + ", ".join(sorted(LIVENESS_KEYS))
    )
PY

echo "OK: $RUNTIME_ID smoke passed"
