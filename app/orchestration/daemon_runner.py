from __future__ import annotations

import time
from dataclasses import dataclass

from app.orchestration.session_builder import UniverseSession


@dataclass
class DaemonResult:
    runtime_id: str
    env: str
    ticks_ran: int


def run_loop(
    *,
    session: UniverseSession,
    max_ticks: int,
    interval_s: float,
    stop_on_exception: bool,
) -> DaemonResult:
    ticks = 0
    try:
        while True:
            if max_ticks > 0 and ticks >= max_ticks:
                break

            try:
                session.run_tick()
            except Exception:
                if stop_on_exception:
                    raise
            ticks += 1

            if interval_s > 0:
                time.sleep(interval_s)
    except KeyboardInterrupt:
        pass

    return DaemonResult(runtime_id=session.runtime_id, env=session.env, ticks_ran=ticks)
