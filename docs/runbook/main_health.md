# Main Health Checklist

This checklist is for local trunk health checks only. It does not upgrade strategy
algorithms and does not place real TqKq orders.

## dev_up / dev_down

- Start the local loop with `scripts/dev_up.sh`.
- Stop it with `scripts/dev_down.sh` before starting another loop.
- `scripts/dev_up.sh` starts three process groups and records pids in `logs/`:
  - `web`: `logs/web.pid`, `logs/web.log`, listens on `127.0.0.1:8000`
  - `prices`: `logs/prices.pid`, `logs/prices.log`, writes `plans/prices.json`
  - `daemon`: `logs/daemon.pid`, `logs/daemon.log`, runs `rt_livefile`
- If the web port is already occupied, stop the existing loop first:
  `scripts/dev_down.sh`.
- If the port is still occupied, locate the holder with:
  `lsof -nP -iTCP:8000 -sTCP:LISTEN`.
- Logs are append-only during the current process lifetime. For a clean local
  check, remove stale logs after shutdown with `rm -f logs/*.log logs/*.pid`.

## Long Run Growth

For a 2-5 minute local smoke run:

```bash
scripts/long_run_smoke.sh
```

The smoke script starts `scripts/dev_up.sh`, waits for `SMOKE_SECONDS` seconds
(`180` by default), calls `python -m tools.inspect_run rt_livefile`, and checks
the web endpoints with `curl`.

Expected growth signals:

- Quote source: `plans/prices.json` should keep receiving quote schema updates.
- Snapshots: `portfolio_snapshots.jsonl` should grow for `rt_livefile`.
- Orders and fills: `order_events.jsonl` and `fill_events.jsonl` should grow
  when the configured strategy emits executable decisions.
- Lifecycle: `order_lifecycle_events.jsonl` grows when broker lifecycle tracking
  emits pending, partial, filled, cancelled, expired, or rejected statuses.
- Rank: `rank_events.jsonl` grows only for plans with `runtime.active_top_n > 0`
  and `runtime.rank_emit_events = 1`.
- Roll: `roll_events.jsonl` grows only when `fixed_main` roll policy observes a
  contract change. Fixed-contract plans should keep it at zero.

Useful manual checks:

```bash
python -m tools.inspect_run rt_livefile --tail 5
curl -fsS http://127.0.0.1:8000/runs/rt_livefile
curl -fsS 'http://127.0.0.1:8000/runs/rt_livefile/events?env=live&tail=20'
tail -n 40 logs/daemon.log
tail -n 40 logs/web.log
```

`tools.inspect_run` and the web readmodel must return warnings for missing
optional artifacts instead of silently hiding them.
