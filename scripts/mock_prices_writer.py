from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path


def build_quote_payload(
    prices: dict[str, float],
    volumes: dict[str, float],
    *,
    ts: int,
) -> dict[str, dict[str, float | int]]:
    return {
        symbol: {
            "price": float(price),
            "volume": float(volumes[symbol]),
            "ts": ts,
        }
        for symbol, price in prices.items()
    }


def _atomic_write_json(path: Path, payload: dict[str, dict[str, float | int]]) -> None:
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

    while True:
        for k, v in list(prices.items()):
            shock = rng.gauss(0.0, float(args.vol))
            dv = float(args.drift) + shock
            prices[k] = max(0.0001, v * (1.0 + dv))

            vshock = abs(rng.gauss(0.0, float(args.volume_vol)))
            volumes[k] = max(0.0, volumes[k] * (1.0 + vshock))

        _atomic_write_json(out_path, build_quote_payload(prices, volumes, ts=int(time.time())))

        if float(args.interval) > 0:
            time.sleep(float(args.interval))

    # unreachable


if __name__ == "__main__":
    raise SystemExit(main())
