from __future__ import annotations

import atexit
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from adapters.marketdata.base import MarketDataAdapter, MarketQuote


def _base_symbol(symbol: str) -> str:
    return symbol[:-5] if symbol.endswith("_main") else symbol


def _parse_ts(dt_val: Any) -> int | None:
    # Tq quote.datetime is usually like "2024-06-17 14:59:59.999500"
    if isinstance(dt_val, str) and dt_val.strip():
        try:
            # tolerate microseconds
            x = dt_val.replace("/", "-")
            return int(datetime.fromisoformat(x).timestamp())
        except Exception:
            return None
    return None


@dataclass
class _State:
    price: float
    raw_volume: float
    ts: int | None


class TqKqMarketData(MarketDataAdapter):
    """
    TqSdk-backed market data adapter.

    - Plan symbols remain base (e.g. "au"); execution may query "au_main".
    - Adapter maps *_main -> base and resolves to a Tq symbol via params mapping.
    - Volume semantics: convert Tq cumulative volume -> per-update delta volume.
    """

    def __init__(
        self,
        *,
        tq_symbols: dict[str, str],
        auth_user: str,
        auth_pass: str,
        api_factory: Callable[[], Any] | None = None,
        start_background: bool = True,
    ) -> None:
        self._tq_symbols = dict(tq_symbols)
        self._lock = threading.Lock()
        self._latest: dict[str, _State] = {}
        self._last_raw_volume: dict[str, float] = {}
        self._stop = threading.Event()

        if api_factory is None:
            # Lazy import so tests can inject fake api without having tqsdk installed.
            from tqsdk import TqApi, TqAuth

            def _factory() -> Any:
                return TqApi(auth=TqAuth(auth_user, auth_pass))

            self._api_factory = _factory
        else:
            self._api_factory = api_factory

        self._api: Any | None = None
        self._quotes: dict[str, Any] = {}
        self._init_api_and_subscribe()
        if start_background:
            self.start()

        atexit.register(self.close)


    def _init_api_and_subscribe(self) -> None:
        if self._api is not None:
            return
        self._api = self._api_factory()
        # subscribe all configured symbols
        for base, tq_sym in self._tq_symbols.items():
            self._quotes[base] = self._api.get_quote(tq_sym)

    def start(self) -> None:
        self._init_api_and_subscribe()

        t = threading.Thread(target=self._loop, name="tqkq_marketdata", daemon=True)
        t.start()

    def close(self) -> None:
        self._stop.set()
        api = self._api
        self._api = None
        if api is not None:
            try:
                api.close()
            except Exception:
                pass

    def _loop(self) -> None:
        assert self._api is not None
        api = self._api
        while not self._stop.is_set():
            try:
                # block until update, but avoid stuck forever
                api.wait_update(deadline=time.time() + 1.0)
                self._poll_once()
            except Exception:
                # do not crash the daemon; keep retrying
                time.sleep(0.2)

    def _poll_once(self) -> None:
        # read all subscribed quotes and update cache
        now_ts: int | None = None
        for base, q in list(self._quotes.items()):
            lp = getattr(q, "last_price", None)
            vol = getattr(q, "volume", None)
            dtv = getattr(q, "datetime", None)
            ts = _parse_ts(dtv)
            if ts is not None:
                now_ts = ts

            if not isinstance(lp, (int, float)):
                continue
            if not isinstance(vol, (int, float)):
                # if volume missing, treat as 0 (still deterministic)
                vol = 0.0

            raw = float(vol)
            prev = self._last_raw_volume.get(base)
            if prev is None or raw < prev:
                delta = 0.0
            else:
                delta = raw - prev
            self._last_raw_volume[base] = raw

            st = _State(price=float(lp), raw_volume=delta, ts=ts)
            with self._lock:
                self._latest[base] = st

        # if no per-symbol ts, still store None
        _ = now_ts

    def _resolve_base(self, symbol: str) -> str:
        base = _base_symbol(symbol)
        if base not in self._tq_symbols:
            raise KeyError(f"tqkq symbol not configured for base={base}")
        return base

    def get_last_quote(self, symbol: str) -> MarketQuote:
        base = self._resolve_base(symbol)
        with self._lock:
            st = self._latest.get(base)
        if st is None:
            raise KeyError(f"no quote yet for symbol={symbol}")
        return MarketQuote(symbol=symbol, price=st.price, volume=st.raw_volume, ts=st.ts)

    def get_last_quotes(self, symbols: list[str]) -> dict[str, MarketQuote]:
        out: dict[str, MarketQuote] = {}
        missing: list[str] = []
        for s in symbols:
            try:
                out[s] = self.get_last_quote(s)
            except KeyError:
                missing.append(s)
        if missing:
            raise KeyError(f"missing quotes: {missing}")
        return out

    def get_quote(self, tq_symbol: str) -> Any:
        """
        Return the raw subscribed quote object for a configured Tq symbol.

        Used by spec providers to read static instrument fields like price_tick
        and volume_multiple without importing tqsdk types.
        """
        for base, sym in self._tq_symbols.items():
            if sym == tq_symbol:
                return self._quotes[base]
        raise KeyError(f"unknown tqkq symbol: {tq_symbol}")
