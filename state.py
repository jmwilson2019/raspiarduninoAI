from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from time import monotonic
from typing import Any, Mapping, Optional


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value == 1:
            return True
        if value == 0:
            return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _coerce_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class HopperState:
    board_id: str = "UNKNOWN"
    timestamp_ms: Optional[int] = None
    ultrasonic_mm: Optional[int] = None
    dust_detected: bool = False
    pir_motion: bool = False
    gate_open: bool = False
    received_monotonic: float = field(default_factory=monotonic)
    raw_payload: Mapping[str, Any] = field(default_factory=dict)

    def data_age_seconds(self) -> float:
        return max(0.0, monotonic() - self.received_monotonic)

    def is_stale(self, stale_after_s: float = 3.0) -> bool:
        return self.data_age_seconds() > stale_after_s


class StateStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._state = HopperState()

    def update_from_payload(self, payload: Mapping[str, Any]) -> HopperState:
        sensors = payload.get("sensors", {}) if isinstance(payload, Mapping) else {}
        sensors_map = sensors if isinstance(sensors, Mapping) else {}
        prior = self.snapshot()

        next_state = HopperState(
            board_id=str(payload.get("board_id", prior.board_id)) if isinstance(payload, Mapping) else prior.board_id,
            timestamp_ms=_coerce_int(payload.get("timestamp"), prior.timestamp_ms) if isinstance(payload, Mapping) else prior.timestamp_ms,
            ultrasonic_mm=_coerce_int(
                sensors_map.get("ultrasonic_mm"),
                prior.ultrasonic_mm,
            ),
            dust_detected=_coerce_bool(
                sensors_map.get("dust"),
                prior.dust_detected,
            ),
            pir_motion=_coerce_bool(
                sensors_map.get("pir_motion"),
                prior.pir_motion,
            ),
            gate_open=_coerce_bool(
                sensors_map.get("gate_open"),
                prior.gate_open,
            ),
            received_monotonic=monotonic(),
            raw_payload=dict(payload) if isinstance(payload, Mapping) else {},
        )

        with self._lock:
            self._state = next_state
            return self._state

    def snapshot(self) -> HopperState:
        with self._lock:
            return self._state
