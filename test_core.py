"""Unit tests for core.py module."""

import pytest
from time import sleep
from core import HopperCore, CoreConfig, build_default_core, HardwareProtocol
from policies import PolicyEngine, PolicyConfig
from state import StateStore


class MockHardware:
    """Mock hardware for testing."""

    def __init__(self):
        self.gate_commands = []
        self.tele_commands = []

    def send_gate(self, command: str) -> None:
        self.gate_commands.append(command)

    def send_tele(self, command: str) -> None:
        self.tele_commands.append(command)


class TestCoreConfig:
    """Tests for CoreConfig dataclass."""

    def test_default_config(self):
        config = CoreConfig()
        assert config.command_cooldown_s == 1.5

    def test_custom_config(self):
        config = CoreConfig(command_cooldown_s=3.0)
        assert config.command_cooldown_s == 3.0


class TestHopperCore:
    """Tests for HopperCore class."""

    def test_initialization_with_defaults(self):
        hardware = MockHardware()
        core = HopperCore(hardware=hardware)
        assert core.hardware is hardware
        assert isinstance(core.state_store, StateStore)
        assert isinstance(core.policy_engine, PolicyEngine)
        assert isinstance(core.config, CoreConfig)

    def test_initialization_with_custom_components(self):
        hardware = MockHardware()
        state_store = StateStore()
        policy_engine = PolicyEngine()
        config = CoreConfig(command_cooldown_s=2.0)
        logger_calls = []

        core = HopperCore(
            hardware=hardware,
            state_store=state_store,
            policy_engine=policy_engine,
            config=config,
            logger=lambda msg: logger_calls.append(msg)
        )

        assert core.hardware is hardware
        assert core.state_store is state_store
        assert core.policy_engine is policy_engine
        assert core.config is config
        assert core.config.command_cooldown_s == 2.0

    def test_on_sensor_payload_updates_state(self):
        hardware = MockHardware()
        core = HopperCore(hardware=hardware)

        payload = {
            "board_id": "GATE_001",
            "timestamp": 12345,
            "sensors": {
                "ultrasonic_mm": 400,
                "dust": False,
                "gate_open": True
            }
        }

        decision = core.on_sensor_payload(payload)
        state = core.state_store.snapshot()

        assert state.board_id == "GATE_001"
        assert state.ultrasonic_mm == 400
        assert state.dust_detected is False

    def test_on_sensor_payload_triggers_gate_close(self):
        hardware = MockHardware()
        policy_config = PolicyConfig(low_material_distance_mm=500)
        policy_engine = PolicyEngine(policy_config)
        core = HopperCore(hardware=hardware, policy_engine=policy_engine)

        payload = {
            "sensors": {
                "ultrasonic_mm": 600,  # Low material
                "gate_open": True
            }
        }

        decision = core.on_sensor_payload(payload)

        assert decision.gate_command == "CLOSE"
        assert len(hardware.gate_commands) == 1
        assert hardware.gate_commands[0] == "CLOSE"

    def test_command_cooldown_prevents_duplicate(self):
        hardware = MockHardware()
        config = CoreConfig(command_cooldown_s=1.0)
        policy_config = PolicyConfig(low_material_distance_mm=500)
        policy_engine = PolicyEngine(policy_config)
        core = HopperCore(
            hardware=hardware,
            policy_engine=policy_engine,
            config=config
        )

        payload = {
            "sensors": {
                "ultrasonic_mm": 600,
                "gate_open": True
            }
        }

        # First command should be sent
        core.on_sensor_payload(payload)
        assert len(hardware.gate_commands) == 1

        # Immediate second command should be blocked
        core.on_sensor_payload(payload)
        assert len(hardware.gate_commands) == 1  # Still only 1

    def test_command_cooldown_expires(self):
        hardware = MockHardware()
        config = CoreConfig(command_cooldown_s=0.1)  # Short cooldown for test
        policy_config = PolicyConfig(low_material_distance_mm=500)
        policy_engine = PolicyEngine(policy_config)
        core = HopperCore(
            hardware=hardware,
            policy_engine=policy_engine,
            config=config
        )

        payload = {
            "sensors": {
                "ultrasonic_mm": 600,
                "gate_open": True
            }
        }

        # First command
        core.on_sensor_payload(payload)
        assert len(hardware.gate_commands) == 1

        # Wait for cooldown to expire
        sleep(0.15)

        # Second command should now be sent
        core.on_sensor_payload(payload)
        assert len(hardware.gate_commands) == 2

    def test_tick_evaluates_current_state(self):
        hardware = MockHardware()
        config = CoreConfig(command_cooldown_s=0.01)  # Very short cooldown
        policy_config = PolicyConfig(low_material_distance_mm=500)
        policy_engine = PolicyEngine(policy_config)
        core = HopperCore(
            hardware=hardware,
            policy_engine=policy_engine,
            config=config
        )

        # Update state
        payload = {
            "sensors": {
                "ultrasonic_mm": 600,
                "gate_open": True
            }
        }
        core.on_sensor_payload(payload)

        # Clear previous commands and wait for cooldown
        hardware.gate_commands.clear()
        sleep(0.05)  # Wait for cooldown to expire

        # Manually trigger evaluation
        decision = core.tick()

        assert decision.gate_command == "CLOSE"
        assert len(hardware.gate_commands) == 1

    def test_logger_called_on_commands(self):
        hardware = MockHardware()
        logger_calls = []
        policy_config = PolicyConfig(low_material_distance_mm=500)
        policy_engine = PolicyEngine(policy_config)
        core = HopperCore(
            hardware=hardware,
            policy_engine=policy_engine,
            logger=lambda msg: logger_calls.append(msg)
        )

        payload = {
            "sensors": {
                "ultrasonic_mm": 600,
                "gate_open": True
            }
        }

        core.on_sensor_payload(payload)

        assert len(logger_calls) >= 1
        assert any("gate command" in msg for msg in logger_calls)

    def test_logger_called_on_alerts(self):
        hardware = MockHardware()
        logger_calls = []
        policy_config = PolicyConfig(low_material_distance_mm=500)
        policy_engine = PolicyEngine(policy_config)
        core = HopperCore(
            hardware=hardware,
            policy_engine=policy_engine,
            logger=lambda msg: logger_calls.append(msg)
        )

        payload = {
            "sensors": {
                "ultrasonic_mm": 600,
                "gate_open": False  # Gate closed, so no command
            }
        }

        core.on_sensor_payload(payload)

        # Should log alert even without command
        assert any("policy alert" in msg for msg in logger_calls)

    def test_different_channel_commands_independent(self):
        hardware = MockHardware()
        config = CoreConfig(command_cooldown_s=1.0)
        core = HopperCore(hardware=hardware, config=config)

        # Simulate sending gate command
        core.hardware.send_gate("CLOSE")
        core._mark_sent("gate", "CLOSE")

        # Should be able to send tele command immediately (different channel)
        assert core._can_send("tele", "PARK")

    def test_prune_command_cache(self):
        hardware = MockHardware()
        config = CoreConfig(command_cooldown_s=0.01)  # Very short cooldown
        core = HopperCore(hardware=hardware, config=config)

        # Mark command sent
        core._mark_sent("gate", "CLOSE")
        assert len(core._last_sent_at) == 1

        # Wait for cache retention to expire
        # Cache is retained for cooldown * 10, with min of 5s
        # So with 0.01s cooldown, retention is max(0.1, 5.0) = 5.0s
        sleep(5.5)

        # Prune should remove old entries
        core._prune_command_cache()
        assert len(core._last_sent_at) == 0


class TestBuildDefaultCore:
    """Tests for build_default_core helper function."""

    def test_requires_hardware(self):
        with pytest.raises(ValueError, match="hardware instance is required"):
            build_default_core(hardware=None)

    def test_builds_with_hardware(self):
        hardware = MockHardware()
        core = build_default_core(hardware=hardware)
        assert isinstance(core, HopperCore)
        assert core.hardware is hardware

    def test_uses_print_logger_by_default(self):
        hardware = MockHardware()
        core = build_default_core(hardware=hardware)
        # Logger is set to print by default
        assert core.logger is print

    def test_accepts_custom_logger(self):
        hardware = MockHardware()
        custom_logger = lambda msg: None
        core = build_default_core(hardware=hardware, logger=custom_logger)
        assert core.logger is custom_logger
