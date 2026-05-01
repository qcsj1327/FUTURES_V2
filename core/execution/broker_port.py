from __future__ import annotations

from typing import Protocol

from domain.execution import ExecutionOrder, ExecutionResult


class BrokerPort(Protocol):
    def submit_order(self, order: ExecutionOrder) -> ExecutionResult: ...
