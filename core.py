from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any, Callable, Mapping, Optional, Protocol

from policies import PolicyDecision, PolicyEngine
from state import StateStore


class HardwareProtocol(Protocol):
    def send_gate(self, command: str) -> None:
        ...

    def send_tele(self, command: str) -> None:
        ...


@dataclass
class CoreConfig:
    command_cooldown_s: float = 1.5


class HopperCore:
    def __init__(
        self,
        hardware: HardwareProtocol,
        state_store: Optional[StateStore] = None,
        policy_engine: Optional[PolicyEngine] = None,
        config: Optional[CoreConfig] = None,
        logger: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.hardware = hardware
        self.state_store = state_store or StateStore()
        self.policy_engine = policy_engine or PolicyEngine()
        self.config = config or CoreConfig()
        self.logger = logger or (lambda _: None)
        self._last_sent_at: dict[str, float] = {}

    def on_sensor_payload(self, payload: Mapping[str, Any]) -> PolicyDecision:
        state = self.state_store.update_from_payload(payload)
        decision = self.policy_engine.evaluate(state)
        self._apply_decision(decision)
        return decision

    def tick(self) -> PolicyDecision:
        state = self.state_store.snapshot()
        decision = self.policy_engine.evaluate(state)
        self._apply_decision(decision)
        return decision

    def _apply_decision(self, decision: PolicyDecision) -> None:
        if decision.gate_command and self._can_send("gate", decision.gate_command):
            self.logger(f"sending gate command: {decision.gate_command}")
            self.hardware.send_gate(decision.gate_command)
            self._mark_sent("gate", decision.gate_command)

        if decision.tele_command and self._can_send("tele", decision.tele_command):
            self.logger(f"sending tele command: {decision.tele_command}")
            self.hardware.send_tele(decision.tele_command)
            self._mark_sent("tele", decision.tele_command)

        if decision.alert:
            self.logger(f"policy alert: {decision.alert}")

    def _can_send(self, channel: str, command: str) -> bool:
        key = f"{channel}:{command}"
        last_sent = self._last_sent_at.get(key)
        if last_sent is None:
            return True
        return (monotonic() - last_sent) >= self.config.command_cooldown_s

    def _mark_sent(self, channel: str, command: str) -> None:
        key = f"{channel}:{command}"
        self._last_sent_at[key] = monotonic()


def build_default_core(
    hardware: Optional[HardwareProtocol] = None,
    logger: Optional[Callable[[str], None]] = print,
) -> HopperCore:
    if hardware is None:
        raise ValueError("hardware instance is required to build HopperCore")
    return HopperCore(hardware=hardware, logger=logger)
