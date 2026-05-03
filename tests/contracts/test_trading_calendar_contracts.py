from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from core.instruments.calendar import TradingCalendar, TradingSession


def _ts(value: str) -> int:
    dt = datetime.fromisoformat(value).replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    return int(dt.timestamp())


def test_trading_calendar_day_sessions_for_two_symbols() -> None:
    calendar = TradingCalendar(
        sessions_by_symbol={
            "au": [TradingSession(start="09:00", end="15:00")],
            "ag": [TradingSession(start="10:00", end="11:00")],
        }
    )

    assert calendar.is_trading_time("au", _ts("2026-05-04T09:30:00"))
    assert not calendar.is_trading_time("au", _ts("2026-05-04T08:59:00"))
    assert calendar.is_trading_time("ag", _ts("2026-05-04T10:30:00"))
    assert not calendar.is_trading_time("ag", _ts("2026-05-04T09:30:00"))


def test_trading_calendar_cross_day_night_session() -> None:
    calendar = TradingCalendar(
        sessions_by_symbol={
            "au": [
                TradingSession(start="09:00", end="15:00"),
                TradingSession(start="21:00", end="02:30"),
            ],
            "ag": [TradingSession(start="21:00", end="02:30")],
        }
    )

    assert calendar.is_trading_time("au", _ts("2026-05-04T21:30:00"))
    assert calendar.is_trading_time("au", _ts("2026-05-05T01:30:00"))
    assert calendar.is_trading_time("ag", _ts("2026-05-05T02:30:00"))
    assert not calendar.is_trading_time("ag", _ts("2026-05-05T03:00:00"))
