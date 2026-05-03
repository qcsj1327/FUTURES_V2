#!/usr/bin/env bash
set -euo pipefail

mkdir -p logs

# 启动 Web（/ui + API）
nohup uvicorn web.server:app --host 127.0.0.1 --port 8000 --reload \
  > logs/web.log 2>&1 & echo $! > logs/web.pid

# 启动 mock prices writer（写 plans/prices.json）
nohup python scripts/mock_prices_writer.py \
  --path plans/prices.json --interval 1 --seed 7 --au 180 --ag 50 \
  > logs/prices.log 2>&1 & echo $! > logs/prices.pid

# 启动 daemon（live_file 读 prices.json，周期写 artifacts）
nohup python -m scripts.run_daemon \
  --config plans/dev.live_file.json \
  --runtime-id rt_livefile \
  --env live \
  --max-ticks 0 \
  --interval 1 \
  --artifact-every 5 \
  --clean \
  > logs/daemon.log 2>&1 & echo $! > logs/daemon.pid

echo "OK"
echo "Web:   http://127.0.0.1:8000/ui/"
echo "Logs:  logs/web.log logs/prices.log logs/daemon.log"
