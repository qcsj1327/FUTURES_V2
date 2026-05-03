from __future__ import annotations

from scripts.mock_prices_writer import build_prices_payload


def test_mock_prices_writer_payload_has_no_main_keys() -> None:
    payload = build_prices_payload({"au": 1.0, "ag": 2.0})
    assert payload == {"au": 1.0, "ag": 2.0}
    assert all(not k.endswith("_main") for k in payload)
