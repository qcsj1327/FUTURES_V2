from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.instruments.calendar import base_symbol


class RollEventSink(Protocol):
    def append_roll_event(self, event: dict[str, object], *, env: str) -> None: ...


@dataclass(frozen=True)
class RollEvent:
    runtime_id: str
    base_symbol: str
    from_contract: str | None
    to_contract: str
    ts: int
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "event_type": "roll",
            "runtime_id": self.runtime_id,
            "base_symbol": self.base_symbol,
            "from_contract": self.from_contract,
            "to_contract": self.to_contract,
            "ts": self.ts,
            "reason": self.reason,
        }


class RollPolicy:
    def __init__(
        self,
        *,
        mode: str,
        contracts: dict[str, str],
        runtime_id: str,
        env: str,
        sink: RollEventSink | None = None,
    ) -> None:
        if mode not in {"fixed_contract", "fixed_main"}:
            raise ValueError(f"invalid roll_policy.mode: {mode}")
        self.mode = mode
        self.contracts = dict(contracts)
        self.runtime_id = runtime_id
        self.env = env
        self.sink = sink
        self._active: dict[str, str] = {}

    def resolve(self, symbol: str, ts: int) -> str:
        base = base_symbol(symbol)
        configured = self.contracts.get(base)
        if not configured:
            raise KeyError(f"missing contract mapping for symbol={base}")

        previous = self._active.get(base)
        if previous is None:
            self._active[base] = configured
            return configured

        if self.mode == "fixed_contract":
            return previous

        if previous != configured:
            self._active[base] = configured
            self._write_roll_event(
                RollEvent(
                    runtime_id=self.runtime_id,
                    base_symbol=base,
                    from_contract=previous,
                    to_contract=configured,
                    ts=ts,
                    reason="fixed_main_contract_changed",
                )
            )
        return self._active[base]

    def _write_roll_event(self, event: RollEvent) -> None:
        if self.sink is None:
            return
        self.sink.append_roll_event(event.to_dict(), env=self.env)
