from __future__ import annotations

from dataclasses import dataclass

from core.instruments.spec_provider import TqKqSpecProvider


@dataclass
class FakeQuote:
    price_tick: float | None = None
    volume_multiple: float | None = None


class FakeTqApi:
    def __init__(self, quotes: dict[str, FakeQuote]) -> None:
        self._quotes = dict(quotes)

    def get_quote(self, tq_symbol: str) -> FakeQuote:
        return self._quotes[tq_symbol]


def test_tqkq_spec_provider_loads_tick_and_multiplier_overrides() -> None:
    api = FakeTqApi(
        quotes={
            "SHFE.au2406": FakeQuote(price_tick=0.2, volume_multiple=1000.0),
        }
    )
    provider = TqKqSpecProvider(
        tq_symbols={"au": "SHFE.au2406"},
        quote_getter=api.get_quote,
    )
    overrides = provider.load_overrides(base_symbols=["au"])
    assert overrides == {"au": {"tick_size": 0.2, "multiplier": 1000.0}}


def test_tqkq_spec_provider_omits_missing_fields_in_overrides() -> None:
    api = FakeTqApi(
        quotes={
            "SHFE.au2406": FakeQuote(price_tick=None, volume_multiple=10.0),
        }
    )
    provider = TqKqSpecProvider(
        tq_symbols={"au": "SHFE.au2406"},
        quote_getter=api.get_quote,
    )
    overrides = provider.load_overrides(base_symbols=["au"])
    assert overrides == {"au": {"multiplier": 10.0}}

