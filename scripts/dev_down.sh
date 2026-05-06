#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p logs

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

  kill -TERM "-$pid" 2>/dev/null || true
  sleep 0.8

  if pgrep -g "$pid" >/dev/null 2>&1; then
    kill -KILL "-$pid" 2>/dev/null || true
    sleep 0.2
  fi

  if pgrep -g "$pid" >/dev/null 2>&1; then
    echo "[FAIL] $name (process group $pid still alive)"
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
    kill "-$signal" "$pid" 2>/dev/null || true
  done < <(pgrep -f "$pattern" || true)
}

cleanup_web_port() {
  local port="${WEB_PORT:-8000}"
  while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue
    [[ "$pid" == "$$" ]] && continue
    echo "[TERM] tcp:$port pid=$pid"
    kill -TERM "$pid" 2>/dev/null || true
  done < <(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
}

shopt -s nullglob
for pidfile in logs/*.pid; do
  stop_pidfile_group "$pidfile"
done
shopt -u nullglob

echo "----"
echo "[SWEEP] matching leftover local dev/TqKq processes"
patterns=(
  "uvicorn.*web.server:app"
  "python.*scripts\\.run_daemon"
  "python.*scripts/mock_prices_writer\\.py"
  "python.*scripts\\.run_plan"
  "python.*scripts\\.run_local"
  "python.*tools\\.inspect_run"
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
  cleanup_web_port
else
  echo "[SKIP] web port cleanup disabled by DEV_DOWN_SKIP_PORT_CLEANUP=1"
fi

sleep 0.8

if [[ "${DEV_DOWN_SKIP_SWEEP:-0}" != "1" ]]; then
  for pattern in "${patterns[@]}"; do
    sweep_pattern "$pattern" KILL
  done
fi
<<<<<<< HEAD

rm -f logs/*.pid

sleep 0.8

<<<<<<< HEAD
if [[ "${DEV_DOWN_SKIP_SWEEP:-0}" != "1" ]]; then
  for pattern in "${patterns[@]}"; do
    sweep_pattern "$pattern" KILL
  done
fi

rm -f logs/*.pid
=======
for pattern in "${patterns[@]}"; do
  sweep_pattern "$pattern" KILL
done
>>>>>>> 1bdf8bf (chore(dev): unify local mode start stop smoke)
=======
>>>>>>> 24169b3 (test: lock live file bars strategy timeframes and dev scripts)

rm -f logs/*.pid

echo "----"
echo "Done"
echo "Verify no leftovers with:"
echo 'pgrep -fl "uvicorn|run_daemon|mock_prices_writer|run_plan|run_local|inspect_run|tqsdk|TqApi" | sort'
