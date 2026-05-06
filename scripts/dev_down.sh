#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p logs

PYTHON_BIN="${PYTHON:-python}"
WEB_PORT="${WEB_PORT:-8000}"

load_dotenv() {
  local dotenv_paths=("$ROOT/.env" "$ROOT/.env.local")
  local dotenv
  local value

  [[ -n "${WEB_PORT:-}" && "$WEB_PORT" != "8000" ]] && return

  for dotenv in "${dotenv_paths[@]}"; do
    [[ -f "$dotenv" ]] || continue
    value="$($PYTHON_BIN - "$dotenv" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
result = ""
for raw_line in path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#"):
        continue
    if line.startswith("export "):
        line = line[7:].lstrip()
    if "=" not in line:
        continue
    key, raw_value = line.split("=", 1)
    key = key.strip()
    if key != "WEB_PORT":
        continue
    raw_value = raw_value.strip()
    if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] and raw_value[0] in {'"', "'"}:
        raw_value = raw_value[1:-1]
    if re.fullmatch(r"[0-9]+", raw_value):
        result = raw_value
print(result, end="")
PY
)"
    if [[ -n "$value" ]]; then
      WEB_PORT="$value"
      export WEB_PORT
      return
    fi
  done
}

stop_pidfile_group() {
  local pidfile="$1"
  local name
  name="$(basename "$pidfile" .pid)"

  if [[ ! -f "$pidfile" ]]; then
    echo "[SKIP] $name (no pid file)"
    return
  fi

  local pid
  pid="$(cat "$pidfile" || true)"
  if [[ -z "${pid:-}" ]]; then
    echo "[SKIP] $name (empty pid)"
    rm -f "$pidfile"
    return
  fi

  kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  sleep 0.8

  if pgrep -g "$pid" >/dev/null 2>&1 || kill -0 "$pid" 2>/dev/null; then
    kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
    sleep 0.2
  fi

  if pgrep -g "$pid" >/dev/null 2>&1 || kill -0 "$pid" 2>/dev/null; then
    echo "[FAIL] $name (process/group $pid still alive)"
  else
    echo "[DOWN] $name (pid=$pid)"
    rm -f "$pidfile"
  fi
}

sweep_pattern() {
  local pattern="$1"
  local signal="$2"
  while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue
    [[ "$pid" == "$$" ]] && continue
    echo "[$signal] $pattern pid=$pid"
    kill -"$signal" "$pid" 2>/dev/null || true
  done < <(pgrep -f "$pattern" || true)
}

cleanup_web_port() {
  local signal="$1"
  local port="${WEB_PORT:-8000}"
  while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue
    [[ "$pid" == "$$" ]] && continue
    echo "[$signal] tcp:$port pid=$pid"
    kill -"$signal" "$pid" 2>/dev/null || true
  done < <(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
}

load_dotenv

shopt -s nullglob
for pidfile in logs/*.pid; do
  stop_pidfile_group "$pidfile"
done
shopt -u nullglob

echo "----"
echo "[SWEEP] matching leftover local dev/TqKq processes"
patterns=(
  "uvicorn.*web.server:app"
  "python.*scripts\.run_daemon"
  "python.*scripts/mock_prices_writer\.py"
  "python.*scripts\.run_plan"
  "python.*scripts\.run_local"
  "python.*tools\.inspect_run"
  "tqsdk"
  "TqApi"
)

if [[ "${DEV_DOWN_SKIP_SWEEP:-0}" != "1" ]]; then
  for pattern in "${patterns[@]}"; do
    sweep_pattern "$pattern" TERM
  done
else
  echo "[SKIP] process sweep disabled by DEV_DOWN_SKIP_SWEEP=1"
fi

if [[ "${DEV_DOWN_SKIP_PORT_CLEANUP:-0}" != "1" ]]; then
  cleanup_web_port TERM
else
  echo "[SKIP] web port cleanup disabled by DEV_DOWN_SKIP_PORT_CLEANUP=1"
fi

sleep 0.8

if [[ "${DEV_DOWN_SKIP_SWEEP:-0}" != "1" ]]; then
  for pattern in "${patterns[@]}"; do
    sweep_pattern "$pattern" KILL
  done
fi

if [[ "${DEV_DOWN_SKIP_PORT_CLEANUP:-0}" != "1" ]]; then
  cleanup_web_port KILL
fi

rm -f logs/*.pid

echo "----"
echo "Done"
echo "Verify no leftovers with:"
echo 'pgrep -fl "uvicorn|run_daemon|mock_prices_writer|run_plan|run_local|inspect_run|tqsdk|TqApi" | sort'
echo "lsof -nP -iTCP:${WEB_PORT} -sTCP:LISTEN"