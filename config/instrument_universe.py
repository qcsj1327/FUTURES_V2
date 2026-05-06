from __future__ import annotations

from typing import TypeVar

T = TypeVar("T")

DEFAULT_SYMBOLS: tuple[str, ...] = ("au", "ag", "cu", "rb", "zn")

DEFAULT_TRADE_CONTRACTS: dict[str, str] = {
    "au": "SHFE.au2606",
    "ag": "SHFE.ag2606",
    "cu": "SHFE.cu2606",
    "rb": "SHFE.rb2610",
    "zn": "SHFE.zn2606",
}

DEFAULT_MAIN_QUOTES: dict[str, str] = {
    symbol: f"KQ.m@SHFE.{symbol}" for symbol in DEFAULT_SYMBOLS
}

DEFAULT_START_PRICES: dict[str, float] = {
    "au": 1030.0,
    "ag": 8200.0,
    "cu": 82000.0,
    "rb": 3300.0,
    "zn": 24000.0,
}

DEFAULT_START_VOLUMES: dict[str, float] = {
    "au": 1000.0,
    "ag": 1100.0,
    "cu": 1200.0,
    "rb": 1300.0,
    "zn": 1400.0,
}

DEFAULT_LOCAL_QUOTE_PROFILES: dict[str, dict[str, float]] = {
    "au": {
        "drift": 0.00002,
        "price_vol": 0.0018,
        "volume_vol": 0.08,
        "mean_reversion": 0.08,
        "seasonality": 0.18,
        "spread_bps": 1.2,
        "jump_probability": 0.006,
        "jump_scale": 0.004,
        "open_interest": 180000.0,
    },
    "ag": {
        "drift": 0.00001,
        "price_vol": 0.0026,
        "volume_vol": 0.12,
        "mean_reversion": 0.06,
        "seasonality": 0.22,
        "spread_bps": 1.8,
        "jump_probability": 0.008,
        "jump_scale": 0.006,
        "open_interest": 420000.0,
    },
    "cu": {
        "drift": -0.00001,
        "price_vol": 0.0034,
        "volume_vol": 0.10,
        "mean_reversion": 0.05,
        "seasonality": 0.16,
        "spread_bps": 2.0,
        "jump_probability": 0.010,
        "jump_scale": 0.007,
        "open_interest": 95000.0,
    },
    "rb": {
        "drift": 0.00003,
        "price_vol": 0.0042,
        "volume_vol": 0.18,
        "mean_reversion": 0.04,
        "seasonality": 0.30,
        "spread_bps": 2.5,
        "jump_probability": 0.012,
        "jump_scale": 0.009,
        "open_interest": 2200000.0,
    },
    "zn": {
        "drift": -0.00002,
        "price_vol": 0.0030,
        "volume_vol": 0.11,
        "mean_reversion": 0.07,
        "seasonality": 0.20,
        "spread_bps": 2.2,
        "jump_probability": 0.009,
        "jump_scale": 0.006,
        "open_interest": 140000.0,
    },
}

SHFE_DAY_SESSIONS: tuple[dict[str, str], ...] = (
    {"start": "09:00", "end": "10:15"},
    {"start": "10:30", "end": "11:30"},
    {"start": "13:30", "end": "15:00"},
)

DEFAULT_TRADING_SESSIONS: dict[str, tuple[dict[str, str], ...]] = {
    "au": (*SHFE_DAY_SESSIONS, {"start": "21:00", "end": "02:30"}),
    "ag": (*SHFE_DAY_SESSIONS, {"start": "21:00", "end": "02:30"}),
    "cu": (*SHFE_DAY_SESSIONS, {"start": "21:00", "end": "01:00"}),
    "rb": (*SHFE_DAY_SESSIONS, {"start": "21:00", "end": "23:00"}),
    "zn": (*SHFE_DAY_SESSIONS, {"start": "21:00", "end": "01:00"}),
}


def default_symbols() -> list[str]:
    return list(DEFAULT_SYMBOLS)


def trade_contracts_for(symbols: list[str]) -> dict[str, str]:
    return _select(DEFAULT_TRADE_CONTRACTS, symbols, "trade contract")


def main_quotes_for(symbols: list[str]) -> dict[str, str]:
    return _select(DEFAULT_MAIN_QUOTES, symbols, "main quote")


def start_prices_for(symbols: list[str]) -> dict[str, float]:
    return _select(DEFAULT_START_PRICES, symbols, "start price")


def start_volumes_for(symbols: list[str]) -> dict[str, float]:
    return _select(DEFAULT_START_VOLUMES, symbols, "start volume")


def local_quote_profiles_for(symbols: list[str]) -> dict[str, dict[str, float]]:
    return _select(DEFAULT_LOCAL_QUOTE_PROFILES, symbols, "local quote profile")


def trading_sessions_for(symbols: list[str]) -> dict[str, list[dict[str, str]]]:
    selected = _select(DEFAULT_TRADING_SESSIONS, symbols, "trading session")
    return {
        symbol: [dict(session) for session in sessions]
        for symbol, sessions in selected.items()
    }


def _select(source: dict[str, T], symbols: list[str], label: str) -> dict[str, T]:
    missing = [symbol for symbol in symbols if symbol not in source]
    if missing:
        raise ValueError(f"missing default {label} mapping for symbols: {missing}")
    return {symbol: source[symbol] for symbol in symbols}
