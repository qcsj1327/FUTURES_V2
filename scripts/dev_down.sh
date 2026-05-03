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
echo "Done"