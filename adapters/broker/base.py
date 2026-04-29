from __future__ import annotations

from abc import ABC, abstractmethod

from domain.execution import ExecutionOrder, ExecutionResult


class BrokerAdapter(ABC):
    @abstractmethod
    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        pass
