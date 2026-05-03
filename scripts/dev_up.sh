#!/usr/bin/env bash
set -euo pipefail

mkdir -p logs

start() {
  local name="$1"
  shift

  python -c '
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
    tail -n 5 "logs/${name}.log" 2>/dev/null || true
  fi
}

start web uvicorn web.server:app --host 127.0.0.1 --port 8000 --reload

start prices python scripts/mock_prices_writer.py \
  --path plans/prices.json --interval 1 --seed 7 --au 180 --ag 50

start daemon python -m scripts.run_daemon \
  --config plans/dev.live_file.json \
  --runtime-id rt_livefile \
  --env live \
  --max-ticks 0 \
  --interval 1 \
  --artifact-every 5 \
  --clean

echo "----"
echo "Web:  http://127.0.0.1:8000/ui/"
echo "Logs: logs/*.log"