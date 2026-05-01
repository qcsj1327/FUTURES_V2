from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class CandidateConfig:
    strategy_name: str
    params: dict[str, Any]


@dataclass(frozen=True)
class CandidateRecord:
    candidate_id: str
    config: CandidateConfig
    metrics: dict[str, Any]


class InMemoryCandidateRegistry:
    def __init__(self) -> None:
        self._records: list[CandidateRecord] = []

    def add(self, *, config: CandidateConfig, metrics: dict[str, Any]) -> CandidateRecord:
        rec = CandidateRecord(candidate_id=str(uuid4()), config=config, metrics=dict(metrics))
        self._records.append(rec)
        return rec

    def all(self) -> list[CandidateRecord]:
        return list(self._records)

    def latest(self) -> CandidateRecord | None:
        if not self._records:
            return None
        return self._records[-1]
