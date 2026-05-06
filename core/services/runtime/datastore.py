from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from core.services.runtime.event_codec import CANONICAL_SCOPES, ENVELOPE_ONLY_FIELDS


class DataStoreError(Exception):
    """Base error for datastore operations."""


class ScopeMismatchError(DataStoreError):
    """Raised when an operation targets a store for a different scope."""


class InvalidWriteError(DataStoreError):
    """Raised when a write is semantically invalid (e.g., non-append-only)."""


class InvalidEventEnvelopeError(InvalidWriteError):
    """Raised when a datastore event does not satisfy envelope + payload rules."""


class DataStore(ABC):
    """
    Runtime side-effect sink. Must be scope-isolated.

    The only runtime scopes are ``local``, ``dryrun``, and ``live``. ``local``
    and ``dryrun`` stores are verification data and must never be read as live
    facts.
    """

    def __init__(self, *, scope: str, runtime_id: str) -> None:
        self.scope = scope
        self.runtime_id = runtime_id

    def _assert_scope(self, scope: str) -> None:
        if scope != self.scope:
            raise ScopeMismatchError(
                f"operation scope={scope} does not match store scope={self.scope}"
            )

    def _validate_event_envelope(
        self,
        event: Mapping[str, Any],
        *,
        scope: str,
        expected_payload_type: str | None = None,
    ) -> None:
        envelope = event.get("envelope")
        payload = event.get("payload")
        if not isinstance(envelope, Mapping):
            raise InvalidEventEnvelopeError("missing envelope")
        if not isinstance(payload, Mapping):
            raise InvalidEventEnvelopeError("missing payload")
        for field in (
            "schema_version",
            "event_id",
            "event_type",
            "runtime_id",
            "runtime_profile",
            "datastore_scope",
            "execution_env",
            "broker_profile",
            "submit_mode",
            "is_live",
            "is_simulated_execution",
            "generated_at",
            "source",
            "payload_type",
        ):
            if envelope.get(field) in (None, ""):
                raise InvalidEventEnvelopeError(f"missing envelope.{field}")
        runtime_profile = envelope.get("runtime_profile")
        datastore_scope = envelope.get("datastore_scope")
        if runtime_profile not in CANONICAL_SCOPES:
            raise InvalidEventEnvelopeError(f"invalid runtime_profile:{runtime_profile}")
        if datastore_scope not in CANONICAL_SCOPES:
            raise InvalidEventEnvelopeError(f"invalid datastore_scope:{datastore_scope}")
        if datastore_scope != scope:
            raise InvalidEventEnvelopeError(
                f"datastore_scope mismatch: envelope={datastore_scope} append={scope}"
            )
        if runtime_profile != datastore_scope:
            raise InvalidEventEnvelopeError(
                f"runtime_profile/datastore_scope mismatch: {runtime_profile}/{datastore_scope}"
            )
        is_live = envelope.get("is_live")
        if not isinstance(is_live, bool):
            raise InvalidEventEnvelopeError("invalid is_live")
        if is_live is not (scope == "live"):
            raise InvalidEventEnvelopeError(f"is_live mismatch for scope:{scope}")
        if not isinstance(envelope.get("is_simulated_execution"), bool):
            raise InvalidEventEnvelopeError("invalid is_simulated_execution")
        submit_mode = envelope.get("submit_mode")
        if submit_mode not in {"none", "dryrun", "live"}:
            raise InvalidEventEnvelopeError(f"invalid submit_mode:{submit_mode}")
        if (
            expected_payload_type is not None
            and envelope.get("payload_type") != expected_payload_type
        ):
            raise InvalidEventEnvelopeError(
                f"payload_type mismatch: envelope={envelope.get('payload_type')} "
                f"expected={expected_payload_type}"
            )
        bad_payload_fields = sorted(set(payload).intersection(ENVELOPE_ONLY_FIELDS))
        if bad_payload_fields:
            raise InvalidEventEnvelopeError(
                "payload contains envelope fields:" + ",".join(bad_payload_fields)
            )

    def _flatten_event_for_read(
        self,
        event: Mapping[str, Any],
        *,
        scope: str | None = None,
        expected_payload_type: str | None = None,
    ) -> dict[str, Any]:
        envelope = event.get("envelope")
        payload = event.get("payload")
        if not isinstance(envelope, Mapping):
            raise InvalidEventEnvelopeError("missing envelope")
        if not isinstance(payload, Mapping):
            raise InvalidEventEnvelopeError("missing payload")
        if scope is not None:
            self._validate_event_envelope(
                event,
                scope=scope,
                expected_payload_type=expected_payload_type,
            )
        return {**dict(payload), **dict(envelope)}

    @abstractmethod
    def append_order_event(self, event: dict[str, Any], *, scope: str) -> None: ...

    @abstractmethod
    def append_fill_event(self, event: dict[str, Any], *, scope: str) -> None: ...

    @abstractmethod
    def append_roll_event(self, event: dict[str, Any], *, scope: str) -> None: ...

    @abstractmethod
    def append_rank_event(self, event: dict[str, Any], *, scope: str) -> None: ...

    @abstractmethod
    def append_strategy_score_event(self, event: dict[str, Any], *, scope: str) -> None: ...

    @abstractmethod
    def append_order_lifecycle_event(self, event: dict[str, Any], *, scope: str) -> None: ...

    @abstractmethod
    def save_portfolio_snapshot(self, *, ts: int, portfolio: Any, scope: str) -> None: ...

    @abstractmethod
    def load_latest_portfolio_snapshot(self, *, scope: str) -> Any | None: ...

    @abstractmethod
    def append_metrics(self, *, ts: int, metrics: Mapping[str, Any], scope: str) -> None: ...

    @abstractmethod
    def read_order_events(self, *, scope: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def read_fill_events(self, *, scope: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def read_roll_events(self, *, scope: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def read_rank_events(self, *, scope: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def read_strategy_score_events(self, *, scope: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def read_order_lifecycle_events(self, *, scope: str) -> list[dict[str, Any]]: ...
