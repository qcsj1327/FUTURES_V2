from __future__ import annotations

from scripts.mock_prices_writer import build_quote_payload


def test_mock_prices_writer_payload_has_quote_schema_and_no_main_keys() -> None:
    payload = build_quote_payload({"au": 1.0, "ag": 2.0}, {"au": 10.0, "ag": 20.0}, ts=7)
    assert payload == {
        "au": {"price": 1.0, "volume": 10.0, "ts": 7},
        "ag": {"price": 2.0, "volume": 20.0, "ts": 7},
    }
    assert all(not k.endswith("_main") for k in payload)
