from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from domain.enums import Decision, PositionSide, Side, SignalStrength
from domain.signal import SignalDecision


class CSVSignalLoader:
    def load(self, path: str | Path) -> Iterable[SignalDecision]:
        with open(path, newline="") as f:
            reader = csv.DictReader(f)

            for row in reader:
                yield SignalDecision(
                    decision=Decision(row["decision"]),
                    side=Side(row["side"]),
                    strength=SignalStrength(row["strength"]),
                    confidence=float(row["confidence"]),
                    reason=row.get("reason", ""),
                    signal_id=row["signal_id"],
                    strategy_name=row["strategy_name"],
                    symbol=row["symbol"],
                    instrument_id=row["instrument_id"],
                    trade_instrument_id=row["trade_instrument_id"],
                    runtime_id=row["runtime_id"],
                    ts=int(row["ts"]),
                    bar_ts=int(row["bar_ts"]),
                    bar_time=row["bar_time"],
                    position_side=PositionSide(row["position_side"]),
                )
