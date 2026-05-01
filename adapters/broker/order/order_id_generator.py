from __future__ import annotations


class OrderIdGenerator:
    def __init__(self, prefix: str = "sim_order") -> None:
        if not prefix:
            raise ValueError("order_id_prefix_required")

        self.prefix = prefix
        self._counter = 0

    def next_id(self) -> str:
        self._counter += 1
        return f"{self.prefix}_{self._counter}"
