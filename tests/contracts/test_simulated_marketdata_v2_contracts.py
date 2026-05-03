from __future__ import annotations

from adapters.marketdata.simulated_market_data_v2 import SimulatedMarketDataV2


def test_simulated_v2_advances_quotes_and_is_deterministic() -> None:
    md1 = SimulatedMarketDataV2(symbols=["au", "ag"], seed=7, drift=0.0, vol=0.01)
    md2 = SimulatedMarketDataV2(symbols=["au", "ag"], seed=7, drift=0.0, vol=0.01)

    p1a = md1.get_last_quotes(["au", "ag"])
    p2a = md2.get_last_quotes(["au", "ag"])
    assert p1a == p2a
    assert p1a["au"].volume is not None

    md1.advance()
    md2.advance()

    p1b = md1.get_last_quotes(["au", "ag"])
    p2b = md2.get_last_quotes(["au", "ag"])
    assert p1b == p2b
    assert p1b != p1a
    assert p1b["au"].ts == 1
