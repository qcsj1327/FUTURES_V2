# Live Shutdown Runbook

This runbook covers local development shutdown only. It does not contain
account credentials and does not change live trading configuration.

## Expected Flow

Start the local stack with:

```bash
scripts/dev_up.sh
```

Stop it with:

```bash
scripts/dev_down.sh
```

`dev_down.sh` stops the pid-file process groups for:

- `web` (`uvicorn`)
- `prices` (`scripts/mock_prices_writer.py`)
- `daemon` (`python -m scripts.run_daemon`)

It then sweeps matching leftover local processes for `uvicorn`,
`run_daemon`, `mock_prices_writer`, `tqsdk`, and `TqApi`.

## Verify Shutdown

After shutdown, run:

```bash
pgrep -fl "uvicorn|run_daemon|mock_prices_writer|tqsdk|TqApi" | sort
```

No project process should remain. If a process still appears, inspect the
command line and kill it explicitly:

```bash
kill -TERM <pid>
sleep 1
kill -KILL <pid>
```

## Logs And Ports

Logs are written under `logs/*.log`. Pid files are written under `logs/*.pid`
and are removed by `dev_down.sh` when the process group exits.

If `uvicorn` does not restart because the port is still occupied, check:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

Then stop the owning process before running `scripts/dev_up.sh` again.

## TqKq Resource Cleanup

The TqKq market data adapter and live broker expose idempotent `close()`
methods. Normal `run_daemon` shutdown calls close on the active session, and
`dev_down.sh` remains the fallback for interrupted local shells.
