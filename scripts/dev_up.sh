#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p logs

MODE="${DEV_START_MODE:-}"
RUNTIME_ID="${DEV_RUNTIME_ID:-}"
AUTO_CONFIRM="${DEV_AUTO_CONFIRM:-0}"
NONINTERACTIVE="${DEV_NONINTERACTIVE:-0}"
PYTHON_BIN="${PYTHON:-python}"
TMP_PLAN=""

usage() {
  cat <<'EOF'
Select local dev mode:
  1) live_file
  2) tqkq_dryrun
  3) tqkq_live_submit
EOF
}

normalize_mode() {
  case "$1" in
    1|live_file) echo "live_file" ;;
    2|tqkq_dryrun) echo "tqkq_dryrun" ;;
    3|tqkq_live_submit) echo "tqkq_live_submit" ;;
    *) return 1 ;;
  esac
}

choose_mode() {
  if [[ -n "$MODE" ]]; then
    normalize_mode "$MODE"
    return
  fi
  if [[ "$NONINTERACTIVE" == "1" ]]; then
    echo "DEV_START_MODE is required when DEV_NONINTERACTIVE=1" >&2
    return 1
  fi
  usage
  read -r -p "Mode [1-3]: " selected
  normalize_mode "$selected"
}

confirm_or_exit() {
  local prompt="$1"
  if [[ "$AUTO_CONFIRM" == "1" ]]; then
    return 0
  fi
  if [[ "$NONINTERACTIVE" == "1" ]]; then
    echo "confirmation required; set DEV_AUTO_CONFIRM=1 for noninteractive runs" >&2
    return 1
  fi
  read -r -p "$prompt [y/N]: " answer
  [[ "$answer" == "y" || "$answer" == "Y" ]]
}

default_runtime_id() {
  case "$1" in
    live_file) echo "rt_livefile" ;;
    tqkq_dryrun) echo "rt_tqkq_dryrun" ;;
    tqkq_live_submit) echo "rt_tqkq_live_submit" ;;
    *) return 1 ;;
  esac
}

derive_live_submit_plan() {
  local runtime_id="$1"
  local token="${DEV_LIVE_CONFIRM_TOKEN:-}"
  if [[ -z "$token" && "$NONINTERACTIVE" != "1" ]]; then
    read -r -p "Type runtime_id to enable live submit ($runtime_id): " token
  fi
  if [[ "$token" != "$runtime_id" ]]; then
    echo "tqkq_live_submit requires confirm token equal to runtime_id" >&2
    return 1
  fi

  TMP_PLAN="$(mktemp "${TMPDIR:-/tmp}/futures_v2_tqkq_live_submit.XXXXXX.json")"
  "$PYTHON_BIN" - "$runtime_id" "$TMP_PLAN" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

runtime_id = sys.argv[1]
out = Path(sys.argv[2])
plan = json.loads(Path("plans/dev.tqkq_live_submit.json").read_text(encoding="utf-8"))
plan.setdefault("adapters", {}).setdefault("broker", {}).setdefault("params", {})
params = plan["adapters"]["broker"]["params"]
params["submit_mode"] = "live"
params["confirm_live"] = True
params["confirm_live_token"] = runtime_id
out.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
  echo "$TMP_PLAN"
}

start() {
  local name="$1"
  shift

  "$PYTHON_BIN" -c '
import os, sys
os.setsid()
os.execvp(sys.argv[1], sys.argv[1:])
' "$@" > "logs/${name}.log" 2>&1 &

  local pid=$!
  echo "$pid" > "logs/${name}.pid"

  sleep 1

  if kill -0 "$pid" 2>/dev/null; then
    echo "[UP]   $name (pid=$pid)"
  else
    echo "[FAIL] $name failed to start"
    echo "       log: logs/${name}.log"
    tail -n 10 "logs/${name}.log" 2>/dev/null || true
    return 1
  fi
}

MODE="$(choose_mode)"
RUNTIME_ID="${RUNTIME_ID:-$(default_runtime_id "$MODE")}"

case "$MODE" in
  live_file)
    PLAN="plans/dev.live_file_bars.json"
    WRITER_ENABLED=1
    ;;
  tqkq_dryrun)
    PLAN="plans/dev.tqkq_live_dryrun_min_loop.json"
    WRITER_ENABLED=0
    ;;
  tqkq_live_submit)
    PLAN="$(derive_live_submit_plan "$RUNTIME_ID")"
    WRITER_ENABLED=0
    ;;
  *)
    echo "unsupported mode: $MODE" >&2
    exit 1
    ;;
esac

cat <<EOF
Local dev startup summary
  mode: $MODE
  runtime_id: $RUNTIME_ID
  plan: $PLAN
  web: http://127.0.0.1:8000/ui/
  mock_prices_writer: $([[ "$WRITER_ENABLED" == "1" ]] && echo enabled || echo disabled)
EOF

if [[ "$MODE" == "tqkq_live_submit" ]]; then
  echo "  submit mode: LIVE (real order submit path; hard gate token matched runtime_id)"
fi

confirm_or_exit "Start local dev stack?" || exit 1

scripts/dev_down.sh >/dev/null 2>&1 || true

start web uvicorn web.server:app --host 127.0.0.1 --port 8000 --reload

if [[ "$WRITER_ENABLED" == "1" ]]; then
  start prices "$PYTHON_BIN" scripts/mock_prices_writer.py \
    --path plans/prices.json --interval 1 --seed 7 --au 180 --ag 50
fi

start daemon "$PYTHON_BIN" -m scripts.run_daemon \
  --config "$PLAN" \
  --runtime-id "$RUNTIME_ID" \
  --env live \
  --max-ticks 0 \
  --interval 1 \
  --artifact-every 5 \
  --clean

if [[ -n "$TMP_PLAN" ]]; then
  rm -f "$TMP_PLAN"
fi

echo "----"
echo "Web:  http://127.0.0.1:8000/ui/?rid=$RUNTIME_ID"
echo "Logs: logs/*.log"
