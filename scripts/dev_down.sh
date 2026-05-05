#!/usr/bin/env bash
set -euo pipefail

stop() {
  local name="$1"
  local pidfile="logs/${name}.pid"

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

for name in daemon prices web; do
  stop "$name"
done

echo "----"
echo "[SWEEP] matching leftover local dev/TqKq processes"
patterns=(
  "uvicorn"
  "python.*run_daemon"
  "python.*mock_prices_writer"
  "tqsdk"
  "TqApi"
)

for pattern in "${patterns[@]}"; do
  while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue
    [[ "$pid" == "$$" ]] && continue
    echo "[TERM] $pattern pid=$pid"
    kill -TERM "$pid" 2>/dev/null || true
  done < <(pgrep -f "$pattern" || true)
done

sleep 0.8

for pattern in "${patterns[@]}"; do
  while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue
    [[ "$pid" == "$$" ]] && continue
    echo "[KILL] $pattern pid=$pid"
    kill -KILL "$pid" 2>/dev/null || true
  done < <(pgrep -f "$pattern" || true)
done

echo "----"
echo "Done"
echo "Verify no leftovers with:"
echo 'pgrep -fl "uvicorn|run_daemon|mock_prices_writer|tqsdk|TqApi" | sort'
