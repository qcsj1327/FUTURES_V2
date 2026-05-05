from __future__ import annotations

import atexit
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from adapters.marketdata.base import MarketDataAdapter, MarketQuote

_API_FACTORY_OVERRIDE: Callable[[], Any] | None = None


def set_tqkq_api_factory_override(factory: Callable[[], Any] | None) -> None:
    """
    Test-only hook: override the internal TqApi factory.

    This avoids importing tqsdk and avoids network access in contracts.
    """
    global _API_FACTORY_OVERRIDE
    _API_FACTORY_OVERRIDE = factory


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
            api_factory = _API_FACTORY_OVERRIDE

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
        self._warmed_up: bool = False
        self._thread: threading.Thread | None = None
        self._init_api_and_subscribe()
        if start_background:
            self.start()

        atexit.register(self.close)

    def warmup(self, symbols: list[str], timeout_s: float) -> None:
        self._init_api_and_subscribe()
        if self._api is None:
            raise ValueError("tqkq api not initialized")

        required = sorted({_base_symbol(s) for s in symbols})
        missing_cfg = [s for s in required if s not in self._tq_symbols]
        if missing_cfg:
            raise ValueError(f"tqkq symbols not configured for bases: {missing_cfg}")

        deadline = time.time() + float(timeout_s)
        while time.time() < deadline:
            try:
                self._api.wait_update(deadline=time.time() + 0.2)
            except Exception:
                time.sleep(0.05)
            self._poll_once()
            with self._lock:
                ok = all(s in self._latest for s in required)
            if ok:
                self._warmed_up = True
                return

        with self._lock:
            missing = [s for s in required if s not in self._latest]
        mapping = {s: self._tq_symbols.get(s) for s in missing}
        raise TimeoutError(
            f"tqkq warmup timeout after {timeout_s}s, missing={missing}, tq_symbols={mapping}"
        )


    def _init_api_and_subscribe(self) -> None:
        if self._api is not None:
            return
        self._api = self._api_factory()
        # subscribe all configured symbols
        for base, tq_sym in self._tq_symbols.items():
            self._quotes[base] = self._api.get_quote(tq_sym)

    def start(self) -> None:
        self._init_api_and_subscribe()
        if self._thread is not None and self._thread.is_alive():
            return

        t = threading.Thread(target=self._loop, name="tqkq_marketdata", daemon=True)
        self._thread = t
        t.start()

    def close(self) -> None:
        self._stop.set()
        api = self._api
        self._api = None
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
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
        if not self._warmed_up:
            raise ValueError(
                "tqkq marketdata not ready, call warmup(symbols, timeout_s) "
                "or set warmup_seconds in plan params"
            )
        with self._lock:
            st = self._latest.get(base)
        if st is None:
            raise ValueError(f"tqkq quote missing for symbol={symbol} (base={base})")
        return MarketQuote(symbol=symbol, price=st.price, volume=st.raw_volume, ts=st.ts)

    def get_last_quotes(self, symbols: list[str]) -> dict[str, MarketQuote]:
        if not self._warmed_up:
            raise ValueError(
                "tqkq marketdata not ready, call warmup(symbols, timeout_s) "
                "or set warmup_seconds in plan params"
            )
        out: dict[str, MarketQuote] = {}
        missing: list[str] = []
        for s in symbols:
            try:
                out[s] = self.get_last_quote(s)
            except ValueError:
                missing.append(s)
        if missing:
            mapping = {m: self._tq_symbols.get(_base_symbol(m)) for m in missing}
            raise ValueError(f"tqkq missing quotes: {missing}, tq_symbols={mapping}")
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
