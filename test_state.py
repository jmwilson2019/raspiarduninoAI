"""Unit tests for state.py module."""

import pytest
from time import sleep
from state import HopperState, StateStore, _coerce_bool, _coerce_int


class TestCoerceBool:
    """Tests for _coerce_bool helper function."""

    def test_bool_passthrough(self):
        assert _coerce_bool(True) is True
        assert _coerce_bool(False) is False

    def test_int_conversion(self):
        assert _coerce_bool(1) is True
        assert _coerce_bool(0) is False
        assert _coerce_bool(2, default=True) is True  # Invalid int uses default

    def test_string_conversion(self):
        # Truthy strings
        assert _coerce_bool("true") is True
        assert _coerce_bool("TRUE") is True
        assert _coerce_bool("1") is True
        assert _coerce_bool("yes") is True
        assert _coerce_bool("on") is True
        # Falsy strings
        assert _coerce_bool("false") is False
        assert _coerce_bool("FALSE") is False
        assert _coerce_bool("0") is False
        assert _coerce_bool("no") is False
        assert _coerce_bool("off") is False

    def test_default_behavior(self):
        assert _coerce_bool(None) is False
        assert _coerce_bool("invalid") is False
        assert _coerce_bool("invalid", default=True) is True


class TestCoerceInt:
    """Tests for _coerce_int helper function."""

    def test_none_handling(self):
        assert _coerce_int(None) is None
        assert _coerce_int(None, default=42) == 42

    def test_int_passthrough(self):
        assert _coerce_int(100) == 100
        assert _coerce_int(0) == 0
        assert _coerce_int(-50) == -50

    def test_string_conversion(self):
        assert _coerce_int("123") == 123
        assert _coerce_int("-456") == -456

    def test_invalid_conversion(self):
        assert _coerce_int("invalid") is None
        assert _coerce_int("invalid", default=99) == 99
        assert _coerce_int(3.14, default=3) == 3  # Float conversion works


class TestHopperState:
    """Tests for HopperState dataclass."""

    def test_default_state(self):
        state = HopperState()
        assert state.board_id == "UNKNOWN"
        assert state.timestamp_ms is None
        assert state.ultrasonic_mm is None
        assert state.dust_detected is False
        assert state.pir_motion is False
        assert state.gate_open is False

    def test_custom_state(self):
        state = HopperState(
            board_id="GATE_001",
            timestamp_ms=12345,
            ultrasonic_mm=500,
            dust_detected=True,
            pir_motion=False,
            gate_open=True
        )
        assert state.board_id == "GATE_001"
        assert state.timestamp_ms == 12345
        assert state.ultrasonic_mm == 500
        assert state.dust_detected is True
        assert state.gate_open is True

    def test_data_age_seconds(self):
        state = HopperState()
        age1 = state.data_age_seconds()
        assert age1 >= 0.0
        sleep(0.1)
        age2 = state.data_age_seconds()
        assert age2 > age1
        assert age2 >= 0.1

    def test_is_stale(self):
        state = HopperState()
        # Fresh state should not be stale
        assert state.is_stale(stale_after_s=1.0) is False
        # After waiting, should become stale
        sleep(0.2)
        assert state.is_stale(stale_after_s=0.1) is True


class TestStateStore:
    """Tests for StateStore class."""

    def test_initial_state(self):
        store = StateStore()
        state = store.snapshot()
        assert state.board_id == "UNKNOWN"
        assert state.gate_open is False

    def test_update_from_payload(self):
        store = StateStore()
        payload = {
            "board_id": "GATE_001",
            "timestamp": 12345,
            "sensors": {
                "ultrasonic_mm": 450,
                "dust": True,
                "pir_motion": False,
                "gate_open": True
            }
        }
        state = store.update_from_payload(payload)
        assert state.board_id == "GATE_001"
        assert state.timestamp_ms == 12345
        assert state.ultrasonic_mm == 450
        assert state.dust_detected is True
        assert state.pir_motion is False
        assert state.gate_open is True

    def test_partial_update(self):
        store = StateStore()
        # First update
        payload1 = {
            "board_id": "GATE_001",
            "sensors": {"gate_open": True}
        }
        state1 = store.update_from_payload(payload1)
        assert state1.gate_open is True
        assert state1.ultrasonic_mm is None

        # Second update with different fields
        payload2 = {
            "sensors": {"ultrasonic_mm": 500}
        }
        state2 = store.update_from_payload(payload2)
        assert state2.gate_open is True  # Preserved from previous
        assert state2.ultrasonic_mm == 500  # Updated

    def test_snapshot_returns_current_state(self):
        store = StateStore()
        payload = {"board_id": "TEST", "sensors": {"dust": True}}
        store.update_from_payload(payload)
        snapshot = store.snapshot()
        assert snapshot.board_id == "TEST"
        assert snapshot.dust_detected is True

    def test_invalid_payload_handling(self):
        store = StateStore()
        # Non-dict payload
        state = store.update_from_payload("invalid")
        assert state.board_id == "UNKNOWN"

    def test_thread_safety(self):
        """Basic test that lock is used (prevents obvious race conditions)."""
        store = StateStore()
        payload = {"board_id": "GATE_001", "sensors": {"dust": True}}
        # These operations should not raise exceptions
        store.update_from_payload(payload)
        store.snapshot()
        store.update_from_payload(payload)
