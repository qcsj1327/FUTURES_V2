from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TIMEFRAME_BUCKETS: dict[str, int] = {
    "5m": 5,
    "15m": 15,
    "1h": 60,
    "1d": 240,
}


@dataclass
class BarAccumulator:
    open: float
    high: float
    low: float
    close: float
    volume: float
    ts: int
    bucket_start_tick: int

    @classmethod
    def from_tick(
        cls,
        *,
        price: float,
        volume: float,
        ts: int,
        tick: int,
    ) -> BarAccumulator:
        return cls(
            open=float(price),
            high=float(price),
            low=float(price),
            close=float(price),
            volume=float(volume),
            ts=int(ts),
            bucket_start_tick=int(tick),
        )

    def update(self, *, price: float, volume: float, ts: int) -> None:
        self.high = max(self.high, float(price))
        self.low = min(self.low, float(price))
        self.close = float(price)
        self.volume += float(volume)
        self.ts = int(ts)

    def payload(self) -> dict[str, float | int]:
        return {
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": float(self.volume),
            "ts": int(self.ts),
        }


BarState = dict[str, dict[str, BarAccumulator]]
QuotePayload = dict[str, dict[str, Any]]


def update_price_volume(
    prices: dict[str, float],
    volumes: dict[str, float],
    *,
    rng: random.Random,
    drift: float,
    vol: float,
    volume_vol: float,
) -> tuple[dict[str, float], dict[str, float]]:
    next_prices: dict[str, float] = {}
    next_volumes: dict[str, float] = {}
    for symbol, price in prices.items():
        shock = rng.gauss(0.0, float(vol))
        dv = float(drift) + shock
        next_prices[symbol] = max(0.0001, float(price) * (1.0 + dv))

        vshock = abs(rng.gauss(0.0, float(volume_vol)))
        next_volumes[symbol] = max(0.0, float(volumes[symbol]) * (1.0 + vshock))
    return next_prices, next_volumes


def update_bar_state(
    bar_state: BarState,
    prices: dict[str, float],
    volumes: dict[str, float],
    *,
    ts: int,
    tick: int,
    timeframe_buckets: dict[str, int] | None = None,
) -> BarState:
    buckets = timeframe_buckets or TIMEFRAME_BUCKETS
    for symbol, price in prices.items():
        symbol_state = bar_state.setdefault(symbol, {})
        for timeframe, bucket_size in buckets.items():
            if bucket_size < 1:
                raise ValueError(f"timeframe bucket must be positive: {timeframe}")
            acc = symbol_state.get(timeframe)
            if acc is None or tick - acc.bucket_start_tick >= bucket_size:
                symbol_state[timeframe] = BarAccumulator.from_tick(
                    price=price,
                    volume=volumes[symbol],
                    ts=ts,
                    tick=tick,
                )
            else:
                acc.update(price=price, volume=volumes[symbol], ts=ts)
    return bar_state


def build_quote_payload(
    prices: dict[str, float],
    volumes: dict[str, float],
    *,
    ts: int,
    bars: BarState | None = None,
) -> QuotePayload:
    return {
        symbol: {
            "price": float(price),
            "volume": float(volumes[symbol]),
            "ts": ts,
            "bars": {
                timeframe: acc.payload()
                for timeframe, acc in sorted((bars or {}).get(symbol, {}).items())
            },
        }
        for symbol, price in prices.items()
    }


def _atomic_write_json(path: Path, payload: QuotePayload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    p = argparse.ArgumentParser(
        prog="mock_prices_writer",
        description="Continuously write quote JSON for live_file market data.",
    )
    p.add_argument(
        "--path",
        type=str,
        default="plans/prices.json",
        help="Output json path (used by live_file).",
    )
    p.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between writes.",
    )
    p.add_argument("--seed", type=int, default=7)
    p.add_argument(
        "--drift",
        type=float,
        default=0.0,
        help="Per-tick drift in pct (e.g. 0.0001).",
    )
    p.add_argument(
        "--vol",
        type=float,
        default=0.005,
        help="Per-tick price volatility in pct (e.g. 0.02).",
    )
    p.add_argument(
        "--volume-vol",
        type=float,
        default=0.02,
        help="Per-tick volume volatility in pct.",
    )
    p.add_argument("--au", type=float, default=180.0, help="Start price for au.")
    p.add_argument("--ag", type=float, default=50.0, help="Start price for ag.")
    p.add_argument("--au-volume", type=float, default=1000.0, help="Start volume for au.")
    p.add_argument("--ag-volume", type=float, default=1000.0, help="Start volume for ag.")
    args = p.parse_args()

    out_path = Path(args.path)
    rng = random.Random(int(args.seed))

    prices: dict[str, float] = {"au": float(args.au), "ag": float(args.ag)}
    volumes: dict[str, float] = {"au": float(args.au_volume), "ag": float(args.ag_volume)}
    bars: BarState = {}
    tick = 0

    while True:
        tick += 1
        ts = int(time.time())
        prices, volumes = update_price_volume(
            prices,
            volumes,
            rng=rng,
            drift=float(args.drift),
            vol=float(args.vol),
            volume_vol=float(args.volume_vol),
        )
        bars = update_bar_state(bars, prices, volumes, ts=ts, tick=tick)
        _atomic_write_json(out_path, build_quote_payload(prices, volumes, ts=ts, bars=bars))

        if float(args.interval) > 0:
            time.sleep(float(args.interval))

    # unreachable


if __name__ == "__main__":
    raise SystemExit(main())
