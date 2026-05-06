from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.instruments.calendar import base_symbol
from core.services.runtime.event_codec import encode_datastore_event


class RollEventSink(Protocol):
    def append_roll_event(self, event: dict[str, object], *, scope: str) -> None: ...


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
        scope: str,
        sink: RollEventSink | None = None,
        close_on_roll: bool = False,
        cooldown_ticks: int = 0,
        main_contract_schedule: dict[str, list[str]] | None = None,
    ) -> None:
        if mode not in {"fixed_contract", "fixed_main"}:
            raise ValueError(f"invalid roll_policy.mode: {mode}")
        if close_on_roll and mode != "fixed_main":
            raise ValueError("roll_policy.close_on_roll requires mode=fixed_main")
        if close_on_roll and cooldown_ticks <= 0:
            raise ValueError("roll_policy.cooldown_ticks must be > 0 when close_on_roll=true")
        self.mode = mode
        self.contracts = dict(contracts)
        self.runtime_id = runtime_id
        self.scope = scope
        self.sink = sink
        self.close_on_roll = close_on_roll
        self.cooldown_ticks = cooldown_ticks
        self.main_contract_schedule = {
            base_symbol(sym): list(values)
            for sym, values in (main_contract_schedule or {}).items()
        }
        self._active: dict[str, str] = {}

    def resolve(self, symbol: str, ts: int) -> str:
        base = base_symbol(symbol)
        configured = self._configured_contract(base, ts)

        previous = self._active.get(base)
        if previous is None:
            self._active[base] = configured
            return configured

        if self.mode == "fixed_contract":
            return previous

        if previous != configured:
            if self.close_on_roll:
                return previous
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

    def roll_intent(self, symbol: str, ts: int) -> tuple[str, str] | None:
        if self.mode != "fixed_main" or not self.close_on_roll:
            return None
        base = base_symbol(symbol)
        desired = self._configured_contract(base, ts)
        current = self._active.get(base)
        if current is None:
            self._active[base] = desired
            return None
        if current == desired:
            return None
        return current, desired

    def activate_roll(
        self,
        symbol: str,
        ts: int,
        *,
        reason: str = "fixed_main_contract_changed",
    ) -> tuple[str, str] | None:
        if self.mode != "fixed_main":
            return None
        base = base_symbol(symbol)
        desired = self._configured_contract(base, ts)
        previous = self._active.get(base)
        if previous is None:
            self._active[base] = desired
            return None
        if previous == desired:
            return None
        self._active[base] = desired
        self._write_roll_event(
            RollEvent(
                runtime_id=self.runtime_id,
                base_symbol=base,
                from_contract=previous,
                to_contract=desired,
                ts=ts,
                reason=reason,
            )
        )
        return previous, desired

    def _configured_contract(self, base: str, ts: int) -> str:
        schedule = self.main_contract_schedule.get(base)
        configured: str | None
        if self.mode == "fixed_main" and schedule:
            idx = max(0, min(int(ts), len(schedule) - 1))
            configured = schedule[idx]
        else:
            configured = self.contracts.get(base)
        if not configured:
            raise KeyError(f"missing contract mapping for symbol={base}")
        return configured

    def _write_roll_event(self, event: RollEvent) -> None:
        if self.sink is None:
            return
        self.sink.append_roll_event(
            encode_datastore_event(
                base={
                    "ts": event.ts,
                    "runtime_id": self.runtime_id,
                    "scope": self.scope,
                    "symbol": event.base_symbol,
                    "strategy_name": "roll_policy",
                    "strategy_id": "roll_policy",
                    "strategy_impl": "RollPolicy",
                },
                event_type="roll",
                payload_type="roll",
                source="roll_policy",
                payload=event.to_dict(),
            ),
            scope=self.scope,
        )
