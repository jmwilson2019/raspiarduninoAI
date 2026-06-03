from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from state import HopperState


@dataclass(frozen=True)
class PolicyConfig:
    stale_after_s: float = 3.0
    low_material_distance_mm: int = 600
    close_on_dust: bool = True
    close_on_motion: bool = False


@dataclass(frozen=True)
class PolicyDecision:
    gate_command: Optional[str] = None
    tele_command: Optional[str] = None
    alert: Optional[str] = None
    reasons: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_actions(self) -> bool:
        return bool(self.gate_command or self.tele_command or self.alert)


class PolicyEngine:
    def __init__(self, config: Optional[PolicyConfig] = None) -> None:
        self.config = config or PolicyConfig()

    def evaluate(self, state: HopperState) -> PolicyDecision:
        reasons: List[str] = []
        gate_command: Optional[str] = None

        if state.is_stale(self.config.stale_after_s):
            reasons.append("sensor_data_stale")
            if state.gate_open:
                gate_command = "CLOSE"

        if self.config.close_on_dust and state.dust_detected:
            reasons.append("dust_detected")
            if state.gate_open:
                gate_command = "CLOSE"

        if self.config.close_on_motion and state.pir_motion:
            reasons.append("pir_motion_detected")
            if state.gate_open:
                gate_command = "CLOSE"

        if (
            state.ultrasonic_mm is not None
            and state.ultrasonic_mm >= self.config.low_material_distance_mm
        ):
            reasons.append("low_material")
            if state.gate_open:
                gate_command = "CLOSE"

        unique_reasons = self._ordered_unique(reasons)
        alert = " | ".join(unique_reasons) if unique_reasons else None

        return PolicyDecision(
            gate_command=gate_command,
            alert=alert,
            reasons=unique_reasons,
        )

    @staticmethod
    def _ordered_unique(values: List[str]) -> Tuple[str, ...]:
        seen = set()
        ordered: List[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return tuple(ordered)
