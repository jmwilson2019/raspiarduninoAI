"""Unit tests for policies.py module."""

import pytest
from policies import PolicyConfig, PolicyDecision, PolicyEngine
from state import HopperState


class TestPolicyDecision:
    """Tests for PolicyDecision dataclass."""

    def test_no_actions(self):
        decision = PolicyDecision()
        assert decision.has_actions is False
        assert decision.gate_command is None
        assert decision.tele_command is None
        assert decision.alert is None

    def test_with_gate_command(self):
        decision = PolicyDecision(gate_command="CLOSE")
        assert decision.has_actions is True
        assert decision.gate_command == "CLOSE"

    def test_with_tele_command(self):
        decision = PolicyDecision(tele_command="PARK")
        assert decision.has_actions is True
        assert decision.tele_command == "PARK"

    def test_with_alert(self):
        decision = PolicyDecision(alert="low_material")
        assert decision.has_actions is True
        assert decision.alert == "low_material"

    def test_with_reasons(self):
        decision = PolicyDecision(reasons=("dust_detected", "low_material"))
        assert len(decision.reasons) == 2
        assert "dust_detected" in decision.reasons


class TestPolicyConfig:
    """Tests for PolicyConfig dataclass."""

    def test_default_config(self):
        config = PolicyConfig()
        assert config.stale_after_s == 3.0
        assert config.low_material_distance_mm == 600
        assert config.close_on_dust is True
        assert config.close_on_motion is False

    def test_custom_config(self):
        config = PolicyConfig(
            stale_after_s=5.0,
            low_material_distance_mm=500,
            close_on_dust=False,
            close_on_motion=True
        )
        assert config.stale_after_s == 5.0
        assert config.low_material_distance_mm == 500
        assert config.close_on_dust is False
        assert config.close_on_motion is True


class TestPolicyEngine:
    """Tests for PolicyEngine class."""

    def test_default_engine(self):
        engine = PolicyEngine()
        assert engine.config.stale_after_s == 3.0

    def test_custom_config(self):
        config = PolicyConfig(stale_after_s=10.0)
        engine = PolicyEngine(config)
        assert engine.config.stale_after_s == 10.0

    def test_normal_state_no_action(self):
        """Normal state should not trigger any actions."""
        engine = PolicyEngine()
        state = HopperState(
            board_id="GATE_001",
            ultrasonic_mm=400,  # Above threshold
            dust_detected=False,
            pir_motion=False,
            gate_open=True
        )
        decision = engine.evaluate(state)
        assert decision.gate_command is None
        assert decision.alert is None

    def test_low_material_closes_gate(self):
        """Low material should trigger gate close."""
        engine = PolicyEngine()
        state = HopperState(
            ultrasonic_mm=650,  # Above 600mm threshold
            gate_open=True
        )
        decision = engine.evaluate(state)
        assert decision.gate_command == "CLOSE"
        assert "low_material" in decision.reasons

    def test_low_material_no_action_if_gate_closed(self):
        """Low material should not trigger action if gate already closed."""
        engine = PolicyEngine()
        state = HopperState(
            ultrasonic_mm=650,
            gate_open=False  # Already closed
        )
        decision = engine.evaluate(state)
        assert decision.gate_command is None
        assert "low_material" in decision.reasons  # Still in alert

    def test_dust_detected_closes_gate(self):
        """Dust detection should close gate when enabled."""
        config = PolicyConfig(close_on_dust=True)
        engine = PolicyEngine(config)
        state = HopperState(
            dust_detected=True,
            gate_open=True
        )
        decision = engine.evaluate(state)
        assert decision.gate_command == "CLOSE"
        assert "dust_detected" in decision.reasons

    def test_dust_detection_disabled(self):
        """Dust should not close gate when disabled."""
        config = PolicyConfig(close_on_dust=False)
        engine = PolicyEngine(config)
        state = HopperState(
            dust_detected=True,
            gate_open=True
        )
        decision = engine.evaluate(state)
        assert decision.gate_command is None

    def test_motion_detected_closes_gate(self):
        """Motion detection should close gate when enabled."""
        config = PolicyConfig(close_on_motion=True)
        engine = PolicyEngine(config)
        state = HopperState(
            pir_motion=True,
            gate_open=True
        )
        decision = engine.evaluate(state)
        assert decision.gate_command == "CLOSE"
        assert "pir_motion_detected" in decision.reasons

    def test_motion_detection_disabled(self):
        """Motion should not close gate when disabled."""
        config = PolicyConfig(close_on_motion=False)
        engine = PolicyEngine(config)
        state = HopperState(
            pir_motion=True,
            gate_open=True
        )
        decision = engine.evaluate(state)
        assert decision.gate_command is None

    def test_stale_data_closes_gate(self):
        """Stale sensor data should close gate."""
        engine = PolicyEngine()
        # Create a state that will be stale
        state = HopperState(gate_open=True)
        # Force staleness by checking with very short threshold
        assert state.is_stale(stale_after_s=0.0)
        decision = engine.evaluate(state)
        assert decision.gate_command == "CLOSE"
        assert "sensor_data_stale" in decision.reasons

    def test_multiple_conditions(self):
        """Multiple conditions should all be reported."""
        config = PolicyConfig(
            close_on_dust=True,
            close_on_motion=True,
            low_material_distance_mm=500
        )
        engine = PolicyEngine(config)
        state = HopperState(
            ultrasonic_mm=600,  # Low material
            dust_detected=True,
            pir_motion=True,
            gate_open=True
        )
        decision = engine.evaluate(state)
        assert decision.gate_command == "CLOSE"
        assert "low_material" in decision.reasons
        assert "dust_detected" in decision.reasons
        assert "pir_motion_detected" in decision.reasons
        assert len(decision.reasons) == 3

    def test_alert_format(self):
        """Alert should format reasons correctly."""
        config = PolicyConfig(close_on_dust=True)
        engine = PolicyEngine(config)
        state = HopperState(
            dust_detected=True,
            ultrasonic_mm=700,
            gate_open=True
        )
        decision = engine.evaluate(state)
        assert decision.alert == "dust_detected | low_material"

    def test_ordered_unique_deduplication(self):
        """_ordered_unique should remove duplicates while preserving order."""
        engine = PolicyEngine()
        result = engine._ordered_unique(["a", "b", "a", "c", "b"])
        assert result == ("a", "b", "c")

    def test_ordered_unique_empty(self):
        """_ordered_unique should handle empty list."""
        engine = PolicyEngine()
        result = engine._ordered_unique([])
        assert result == ()
