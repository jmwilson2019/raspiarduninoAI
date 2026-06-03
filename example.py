#!/usr/bin/env python3
"""
Example usage of the raspiarduninoAI hopper control system.

This demonstrates how to integrate the library with hardware interfaces.
"""

from core import HopperCore, HardwareProtocol, build_default_core
from policies import PolicyConfig, PolicyEngine
from state import StateStore


class MockHardware:
    """Mock hardware implementation for testing/demonstration."""

    def send_gate(self, command: str) -> None:
        """Send command to gate controller."""
        print(f"[GATE] Sending command: {command}")

    def send_tele(self, command: str) -> None:
        """Send command to telescope controller."""
        print(f"[TELE] Sending command: {command}")


def example_basic_usage():
    """Demonstrate basic usage with default configuration."""
    print("=== Basic Usage Example ===\n")

    # Create hardware interface
    hardware = MockHardware()

    # Build core with default settings
    core = build_default_core(hardware=hardware, logger=print)

    # Simulate receiving sensor data from gate board
    sensor_payload = {
        "board_id": "GATE_001",
        "timestamp": 12345,
        "sensors": {
            "ultrasonic_mm": 450,  # Material level OK
            "dust": False,
            "pir_motion": False,
            "gate_open": True
        }
    }

    print("Processing sensor payload (normal conditions):")
    decision = core.on_sensor_payload(sensor_payload)
    print(f"Decision: gate_command={decision.gate_command}, alert={decision.alert}\n")

    # Simulate low material condition
    low_material_payload = {
        "board_id": "GATE_001",
        "timestamp": 12350,
        "sensors": {
            "ultrasonic_mm": 650,  # Low material detected
            "dust": False,
            "pir_motion": False,
            "gate_open": True
        }
    }

    print("Processing sensor payload (low material detected):")
    decision = core.on_sensor_payload(low_material_payload)
    print(f"Decision: gate_command={decision.gate_command}, alert={decision.alert}\n")


def example_custom_policy():
    """Demonstrate usage with custom policy configuration."""
    print("=== Custom Policy Example ===\n")

    # Create custom policy configuration
    custom_policy = PolicyConfig(
        stale_after_s=5.0,
        low_material_distance_mm=500,  # More sensitive threshold
        close_on_dust=True,
        close_on_motion=True  # Enable motion detection
    )

    hardware = MockHardware()
    state_store = StateStore()
    policy_engine = PolicyEngine(config=custom_policy)

    # Create core with custom components
    core = HopperCore(
        hardware=hardware,
        state_store=state_store,
        policy_engine=policy_engine,
        logger=print
    )

    # Test with motion detected
    motion_payload = {
        "board_id": "GATE_001",
        "timestamp": 20000,
        "sensors": {
            "ultrasonic_mm": 400,
            "dust": False,
            "pir_motion": True,  # Motion detected
            "gate_open": True
        }
    }

    print("Processing sensor payload (motion detected):")
    decision = core.on_sensor_payload(motion_payload)
    print(f"Decision: gate_command={decision.gate_command}, alert={decision.alert}\n")


def example_manual_tick():
    """Demonstrate periodic evaluation using tick()."""
    print("=== Manual Tick Example ===\n")

    hardware = MockHardware()
    core = build_default_core(hardware=hardware, logger=print)

    # Update state
    payload = {
        "board_id": "GATE_001",
        "timestamp": 30000,
        "sensors": {
            "ultrasonic_mm": 300,
            "dust": True,  # Dust detected
            "pir_motion": False,
            "gate_open": True
        }
    }
    core.on_sensor_payload(payload)

    # Manually trigger policy evaluation
    print("Manual tick (re-evaluating current state):")
    decision = core.tick()
    print(f"Decision: gate_command={decision.gate_command}, alert={decision.alert}\n")


if __name__ == "__main__":
    example_basic_usage()
    print("-" * 60 + "\n")
    example_custom_policy()
    print("-" * 60 + "\n")
    example_manual_tick()
