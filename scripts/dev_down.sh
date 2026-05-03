#!/usr/bin/env bash
set -euo pipefail

for name in daemon prices web; do
  pidfile="logs/${name}.pid"
  if [[ -f "$pidfile" ]]; then
    pid="$(cat "$pidfile" || true)"
    if [[ -n "${pid:-}" ]]; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$pidfile"
  fi
done

echo "OK"
