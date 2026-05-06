from __future__ import annotations

import argparse
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config.instrument_universe import (
    default_symbols,
    local_quote_profiles_for,
    start_prices_for,
    start_volumes_for,
)

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
QuoteProfiles = dict[str, dict[str, float]]
SymbolRngs = dict[str, random.Random]


def symbol_rngs(symbols: list[str], *, seed: int) -> SymbolRngs:
    return {
        symbol: random.Random(int(seed) + sum((idx + 1) * ord(ch) for idx, ch in enumerate(symbol)))
        for symbol in symbols
    }


def update_price_volume(
    prices: dict[str, float],
    volumes: dict[str, float],
    *,
    rng: random.Random,
    drift: float,
    vol: float,
    volume_vol: float,
    tick: int = 1,
    start_prices: dict[str, float] | None = None,
    profiles: QuoteProfiles | None = None,
    rngs: SymbolRngs | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    next_prices: dict[str, float] = {}
    next_volumes: dict[str, float] = {}
    base_volumes = start_volumes_for(list(prices))
    for symbol, price in prices.items():
        profile = profiles.get(symbol, {}) if profiles else {}
        srng = rngs.get(symbol, rng) if rngs else rng
        symbol_drift = float(profile.get("drift", drift))
        symbol_vol = float(profile.get("price_vol", vol))
        symbol_volume_vol = float(profile.get("volume_vol", volume_vol))
        anchor = (start_prices or prices).get(symbol, price)
        mean_reversion = float(profile.get("mean_reversion", 0.0))
        seasonality = float(profile.get("seasonality", 0.0))
        jump_probability = float(profile.get("jump_probability", 0.0))
        jump_scale = float(profile.get("jump_scale", symbol_vol * 2.0))

        seasonal = seasonality * symbol_vol * math.sin((tick + len(symbol) * 7) / 11.0)
        revert = mean_reversion * ((float(anchor) - float(price)) / max(float(anchor), 0.0001))
        jump = srng.gauss(0.0, jump_scale) if srng.random() < jump_probability else 0.0
        shock = srng.gauss(0.0, symbol_vol)
        dv = symbol_drift + seasonal + revert + shock + jump
        next_prices[symbol] = max(0.0001, float(price) * (1.0 + dv))

        volume_seasonal = 1.0 + float(profile.get("seasonality", 0.0)) * (
            0.5 + 0.5 * math.sin((tick + len(symbol) * 13) / 9.0)
        )
        vshock = srng.lognormvariate(0.0, symbol_volume_vol)
        volume_anchor = float(base_volumes.get(symbol, volumes[symbol]))
        next_volumes[symbol] = max(0.0, volume_anchor * vshock * volume_seasonal)
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
    profiles: QuoteProfiles | None = None,
    previous_prices: dict[str, float] | None = None,
) -> QuotePayload:
    payload: QuotePayload = {}
    for symbol, price in prices.items():
        profile = profiles.get(symbol, {}) if profiles else {}
        previous = (previous_prices or {}).get(symbol, price)
        spread = float(price) * float(profile.get("spread_bps", 1.0)) / 10000.0
        open_interest = float(profile.get("open_interest", 0.0))
        bars_payload = {
            timeframe: {
                **acc.payload(),
                "vwap": _vwap(acc),
                "range": float(acc.high - acc.low),
                "return_pct": _return_pct(acc.open, acc.close),
            }
            for timeframe, acc in sorted((bars or {}).get(symbol, {}).items())
        }
        payload[symbol] = {
            "symbol": symbol,
            "quote_source": "local_simulated",
            "is_simulated": True,
            "price": float(price),
            "latest_market_price": float(price),
            "volume": float(volumes[symbol]),
            "ts": ts,
            "bid_price": max(0.0001, float(price) - spread / 2.0),
            "ask_price": float(price) + spread / 2.0,
            "spread": spread,
            "turnover": float(price) * float(volumes[symbol]),
            "open_interest": open_interest,
            "price_change": float(price) - float(previous),
            "return_pct": _return_pct(previous, price),
            "bars": bars_payload,
        }
    return payload


def build_seed_quote_payload(
    *,
    seed: int = 7,
    ts: int | None = None,
    drift: float = 0.0,
    vol: float = 0.005,
    volume_vol: float = 0.02,
) -> QuotePayload:
    symbols = default_symbols()
    rng = random.Random(int(seed))
    profiles = local_quote_profiles_for(symbols)
    start_prices = start_prices_for(symbols)
    prices, volumes = update_price_volume(
        start_prices,
        start_volumes_for(symbols),
        rng=rng,
        drift=drift,
        vol=vol,
        volume_vol=volume_vol,
        tick=1,
        start_prices=start_prices,
        profiles=profiles,
        rngs=symbol_rngs(symbols, seed=seed),
    )
    quote_ts = int(time.time()) if ts is None else int(ts)
    bars = update_bar_state({}, prices, volumes, ts=quote_ts, tick=1)
    return build_quote_payload(
        prices,
        volumes,
        ts=quote_ts,
        bars=bars,
        profiles=profiles,
        previous_prices=start_prices,
    )


def _vwap(bar: BarAccumulator) -> float:
    return float((bar.open + bar.high + bar.low + bar.close) / 4.0)


def _return_pct(old: float, new: float) -> float:
    if old == 0:
        return 0.0
    return float((new - old) / old)


def _atomic_write_json(path: Path, payload: QuotePayload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    p = argparse.ArgumentParser(
        prog="local_quote_writer",
        description="Continuously write quote JSON for local runtime market data.",
    )
    p.add_argument(
        "--path",
        type=str,
        default="plans/prices.json",
        help="Output json path (used by local_file).",
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
    p.add_argument(
        "--once",
        action="store_true",
        help="Write one quote snapshot and exit.",
    )
    args = p.parse_args()

    out_path = Path(args.path)
    symbols = default_symbols()
    rng = random.Random(int(args.seed))
    rngs = symbol_rngs(symbols, seed=int(args.seed))
    profiles = local_quote_profiles_for(symbols)
    start_prices = start_prices_for(symbols)
    prices: dict[str, float] = dict(start_prices)
    volumes: dict[str, float] = start_volumes_for(symbols)
    bars: BarState = {}
    tick = 0

    while True:
        tick += 1
        ts = int(time.time())
        previous_prices = dict(prices)
        prices, volumes = update_price_volume(
            prices,
            volumes,
            rng=rng,
            drift=float(args.drift),
            vol=float(args.vol),
            volume_vol=float(args.volume_vol),
            tick=tick,
            start_prices=start_prices,
            profiles=profiles,
            rngs=rngs,
        )
        bars = update_bar_state(bars, prices, volumes, ts=ts, tick=tick)
        _atomic_write_json(
            out_path,
            build_quote_payload(
                prices,
                volumes,
                ts=ts,
                bars=bars,
                profiles=profiles,
                previous_prices=previous_prices,
            ),
        )

        if bool(args.once):
            break

        if float(args.interval) > 0:
            time.sleep(float(args.interval))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
