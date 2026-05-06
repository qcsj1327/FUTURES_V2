from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class TradingSession:
    start: str
    end: str

    def start_time(self) -> time:
        return _parse_hhmm(self.start)

    def end_time(self) -> time:
        return _parse_hhmm(self.end)


def _parse_hhmm(value: str) -> time:
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError(f"invalid session time: {value}")
    hour = int(parts[0])
    minute = int(parts[1])
    return time(hour=hour, minute=minute)


class TradingCalendar:
    def __init__(
        self,
        *,
        sessions_by_symbol: dict[str, list[TradingSession]],
        timezone: str = "Asia/Shanghai",
    ) -> None:
        self._sessions = sessions_by_symbol
        self._tz = ZoneInfo(timezone)

    def is_trading_time(self, symbol: str, ts: int) -> bool:
        base = base_symbol(symbol)
        sessions = self._sessions.get(base, [])
        if not sessions:
            return True

        dt = datetime.fromtimestamp(ts, tz=self._tz)
        current = dt.time()
        for session in sessions:
            start = session.start_time()
            end = session.end_time()
            if start <= end:
                if dt.weekday() < 5 and start <= current <= end:
                    return True
            else:
                if current >= start and dt.weekday() < 5:
                    return True
                previous_day = dt - timedelta(days=1)
                if current <= end and previous_day.weekday() < 5:
                    return True
        return False


def base_symbol(symbol: str) -> str:
    if symbol.startswith("KQ.m@"):
        symbol = symbol.removeprefix("KQ.m@")
    if symbol.endswith("_main"):
        symbol = symbol[:-5]
    if "." in symbol:
        symbol = symbol.rsplit(".", 1)[1]
    return "".join(ch for ch in symbol if ch.isalpha()) or symbol
