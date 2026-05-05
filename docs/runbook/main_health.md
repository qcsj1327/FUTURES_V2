# Main Health Checklist

This checklist is for local trunk health checks only. It does not upgrade strategy
algorithms and does not place real TqKq orders.

## Main Gate

Run the full local trunk gate before merging code into `main`:

```bash
PYTHON=.venv/bin/python scripts/check_main.sh
```

The script is the single local entrypoint for:

- `python -m ruff check .`
- `python -m compileall -q .`
- `python -m mypy .`
- `python -m pytest -q`

Focused checks are useful while iterating, but they are not a substitute for this
gate before a mainline merge.

## dev_up / dev_down

- Start the local loop with `scripts/dev_up.sh`.
- Stop it with `scripts/dev_down.sh` before starting another loop.
- `scripts/dev_up.sh` prompts for a local mode unless `DEV_START_MODE` is set:
  - `live_file`: starts web, `mock_prices_writer`, and daemon.
  - `tqkq_dryrun`: starts web and daemon with the TqKq live-broker dry-run plan.
  - `tqkq_live_submit`: starts web and daemon only after the runtime-id hard gate
    token is confirmed; this is the real submit path.
- `tqkq_sim` is intentionally not in the daemon menu because
  `scripts.run_daemon` rejects `runtime.mode=tqkq_sim`.
- `scripts/dev_up.sh` records pids in `logs/`:
  - `web`: `logs/web.pid`, `logs/web.log`, listens on `127.0.0.1:8000`
  - `prices`: `logs/prices.pid`, `logs/prices.log`, writes `plans/prices.json`
    only in `live_file` mode
  - `daemon`: `logs/daemon.pid`, `logs/daemon.log`
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

The smoke script starts `scripts/dev_up.sh` using `DEV_START_MODE`, waits for
`SMOKE_SECONDS` seconds (`180` by default), calls `python -m tools.inspect_run`,
and checks the web endpoints with `curl`.

Examples:

```bash
DEV_START_MODE=live_file SMOKE_SECONDS=60 scripts/long_run_smoke.sh
DEV_START_MODE=tqkq_dryrun SMOKE_SECONDS=60 scripts/long_run_smoke.sh
```

Expected growth signals:

- Quote source: `plans/prices.json` should keep receiving quote schema updates.
- Snapshots: `portfolio_snapshots.jsonl` can grow for the selected runtime.
- Orders and fills: `order_events.jsonl` and `fill_events.jsonl` should grow
  when the configured strategy emits executable decisions.
- Lifecycle: `order_lifecycle_events.jsonl` grows when broker lifecycle tracking
  emits pending, partial, filled, cancelled, expired, or rejected statuses.
- Strategy score: `strategy_score_events.jsonl` grows when strategy scoring is
  enabled.
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
