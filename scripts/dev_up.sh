#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p logs

MODE=""
RUNTIME_ID=""
AUTO_CONFIRM="0"
NONINTERACTIVE="0"
PYTHON_BIN="${PYTHON:-python}"
WEB_PORT="${WEB_PORT:-8000}"
TMP_PLAN=""

load_dotenv() {
  local dotenv_paths=("$ROOT/.env" "$ROOT/.env.local")
  local dotenv
  local parsed
  local assignment
  local key

  for dotenv in "${dotenv_paths[@]}"; do
    [[ -f "$dotenv" ]] || continue

    parsed="$($PYTHON_BIN - "$dotenv" <<'PY'
from __future__ import annotations

import re
import shlex
import sys
from pathlib import Path

path = Path(sys.argv[1])
for raw_line in path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#"):
        continue
    if line.startswith("export "):
        line = line[7:].lstrip()
    if "=" not in line:
        continue
    key, value = line.split("=", 1)
    key = key.strip()
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) is None:
        continue
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    print(f"{key}={shlex.quote(value)}")
PY
)"

    while IFS= read -r assignment; do
      [[ -n "$assignment" ]] || continue
      key="${assignment%%=*}"
      if [[ -z "${!key+x}" ]]; then
        eval "export $assignment"
      fi
    done <<< "$parsed"
  done
}

usage() {
  cat >&2 <<'EOF'
Select local dev mode:
  1) local   - local prices.json writer + simulated submit daemon
  2) dryrun  - TqKq market data + broker dry-run daemon
  3) live    - TqKq live submit path; requires runtime_id token
EOF
}

normalize_mode() {
  case "$1" in
    1|local) echo "local" ;;
    2|dryrun) echo "dryrun" ;;
    3|live) echo "live" ;;
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
    local) echo "rt_local" ;;
    dryrun) echo "rt_dryrun" ;;
    live) echo "rt_live" ;;
    *) return 1 ;;
  esac
}

first_existing_plan() {
  local candidate
  for candidate in "$@"; do
    if [[ -f "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

derive_live_submit_plan() {
  local runtime_id="$1"
  local base_plan
  local token="${DEV_LIVE_CONFIRM_TOKEN:-${TQKQ_LIVE_CONFIRM_TOKEN:-}}"

  base_plan="$(first_existing_plan \
    plans/dev.live.json)" || {
      echo "missing live plan" >&2
      return 1
    }

  if [[ -z "$token" ]]; then
    token="$runtime_id"
  fi

  if [[ "$token" != "$runtime_id" && "$NONINTERACTIVE" != "1" && "$AUTO_CONFIRM" != "1" ]]; then
    read -r -p "Type runtime_id to enable live submit ($runtime_id): " token
  fi

  if [[ "$token" != "$runtime_id" ]]; then
    echo "live requires confirm token equal to runtime_id" >&2
    return 1
  fi

  TMP_PLAN="$(mktemp "${TMPDIR:-/tmp}/futures_v2_live.${runtime_id}.XXXXXX")" || {
    echo "failed to create temp live-submit plan" >&2
    return 1
  }

  "$PYTHON_BIN" - "$runtime_id" "$TMP_PLAN" "$base_plan" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

runtime_id = sys.argv[1]
out = Path(sys.argv[2])
base_plan = Path(sys.argv[3])
plan = json.loads(base_plan.read_text(encoding="utf-8"))

plan.setdefault("runtime", {})
plan["runtime"]["mode"] = "live"

plan.setdefault("adapters", {})
plan["adapters"].setdefault("market_data", {})
plan["adapters"]["market_data"]["mode"] = "tqkq"

plan["adapters"].setdefault("broker", {})
plan["adapters"]["broker"]["mode"] = "tqkq"
plan["adapters"]["broker"].setdefault("params", {})

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
    tail -n 20 "logs/${name}.log" 2>/dev/null || true
    rm -f "logs/${name}.pid"
    return 1
  fi
}

cleanup_tmp_plan() {
  if [[ -n "$TMP_PLAN" && -f "$TMP_PLAN" ]]; then
    rm -f "$TMP_PLAN"
  fi
}
trap cleanup_tmp_plan EXIT

load_dotenv

MODE="${DEV_START_MODE:-$MODE}"
RUNTIME_ID="${DEV_RUNTIME_ID:-$RUNTIME_ID}"
AUTO_CONFIRM="${DEV_AUTO_CONFIRM:-$AUTO_CONFIRM}"
NONINTERACTIVE="${DEV_NONINTERACTIVE:-$NONINTERACTIVE}"
WEB_PORT="${WEB_PORT:-8000}"

MODE="$(choose_mode)"
RUNTIME_ID="${RUNTIME_ID:-$(default_runtime_id "$MODE")}"

case "$MODE" in
  local)
    PLAN="$(first_existing_plan plans/dev.local.json)" || {
      echo "missing local plan" >&2
      exit 1
    }
    WRITER_ENABLED=1
    ;;
  dryrun)
    PLAN="$(first_existing_plan plans/dev.dryrun.json)" || {
      echo "missing dryrun plan" >&2
      exit 1
    }
    WRITER_ENABLED=0
    ;;
  live)
    PLAN="$(derive_live_submit_plan "$RUNTIME_ID")" || exit 1
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
  web: http://127.0.0.1:${WEB_PORT}/ui/#rid=$RUNTIME_ID
  local_quote_writer: $([[ "$WRITER_ENABLED" == "1" ]] && echo enabled || echo disabled)
EOF

if [[ "$MODE" == "live" ]]; then
  echo "  submit mode: LIVE (real order submit path; hard gate token matched runtime_id)"
fi

confirm_or_exit "Start local dev stack?" || exit 1

bash scripts/dev_down.sh >/dev/null 2>&1 || true

if [[ "$WRITER_ENABLED" == "1" ]]; then
  "$PYTHON_BIN" scripts/local_quote_writer.py \
    --path plans/prices.json \
    --seed 7 \
    --once
fi

start web uvicorn web.server:app --host 127.0.0.1 --port "$WEB_PORT" --reload

if [[ "$WRITER_ENABLED" == "1" ]]; then
  start prices "$PYTHON_BIN" scripts/local_quote_writer.py \
    --path plans/prices.json \
    --interval 1 \
    --seed 7
fi

start daemon "$PYTHON_BIN" -m scripts.run_daemon \
  --config "$PLAN" \
  --runtime-id "$RUNTIME_ID" \
  --profile "$MODE" \
  --max-ticks 0 \
  --interval 1 \
  --artifact-every 5 \
  --clean

echo "----"
echo "Web:  http://127.0.0.1:${WEB_PORT}/ui/#rid=$RUNTIME_ID"
echo "Logs: logs/*.log"
