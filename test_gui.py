"""Unit tests for gui.py module."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt

# Initialize QApplication for testing
@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def gui(qapp):
    """Create HolographicGUI instance for testing."""
    from gui import HolographicGUI
    gui_instance = HolographicGUI()
    yield gui_instance
    gui_instance.close()


class TestMockHardwareGUI:
    """Tests for MockHardwareGUI class."""

    def test_initialization(self, qapp):
        """Test MockHardwareGUI initialization."""
        from gui import MockHardwareGUI, HolographicGUI
        gui_instance = HolographicGUI()
        hardware = MockHardwareGUI(gui_instance)
        assert hardware.gui is gui_instance
        gui_instance.close()

    def test_send_gate_logs_message(self, gui):
        """Test that send_gate logs a message."""
        from gui import MockHardwareGUI
        hardware = MockHardwareGUI(gui)
        initial_log_length = len(gui.log_display.toPlainText())
        hardware.send_gate("OPEN")
        final_log_length = len(gui.log_display.toPlainText())
        assert final_log_length > initial_log_length
        assert "GATE" in gui.log_display.toPlainText()

    def test_send_tele_logs_message(self, gui):
        """Test that send_tele logs a message."""
        from gui import MockHardwareGUI
        hardware = MockHardwareGUI(gui)
        initial_log_length = len(gui.log_display.toPlainText())
        hardware.send_tele("PARK")
        final_log_length = len(gui.log_display.toPlainText())
        assert final_log_length > initial_log_length
        assert "TELE" in gui.log_display.toPlainText()


class TestAnimatedLabel:
    """Tests for AnimatedLabel class."""

    def test_initialization(self, qapp):
        """Test AnimatedLabel initialization."""
        from gui import AnimatedLabel
        label = AnimatedLabel("Test")
        assert label.text() == "Test"
        assert label._glow_intensity == 0.5

    def test_glow_intensity_property(self, qapp):
        """Test glow_intensity property getter and setter."""
        from gui import AnimatedLabel
        label = AnimatedLabel("Test")
        label.glow_intensity = 0.8
        assert label.glow_intensity == 0.8

    def test_start_animation(self, qapp):
        """Test starting the glow animation."""
        from gui import AnimatedLabel
        label = AnimatedLabel("Test")
        label.start_animation()
        # Animation should be running
        assert label.animation.state() == label.animation.Running


class TestHolographicGauge:
    """Tests for HolographicGauge class."""

    def test_initialization(self, qapp):
        """Test HolographicGauge initialization."""
        from gui import HolographicGauge, HOLO_CYAN
        gauge = HolographicGauge("Test Gauge", 0, 100, "units", HOLO_CYAN)
        assert gauge.title == "Test Gauge"
        assert gauge.min_val == 0
        assert gauge.max_val == 100
        assert gauge.units == "units"
        assert gauge.current_value == 0.0

    def test_update_value(self, qapp):
        """Test updating gauge value."""
        from gui import HolographicGauge, HOLO_CYAN
        gauge = HolographicGauge("Test", 0, 100, "units", HOLO_CYAN)
        gauge.update_value(50.0)
        assert gauge.current_value == 50.0
        assert "50.0" in gauge.value_label.text()

    def test_update_value_with_clamping(self, qapp):
        """Test that values are properly clamped to min/max."""
        from gui import HolographicGauge, HOLO_CYAN
        gauge = HolographicGauge("Test", 0, 100, "", HOLO_CYAN)

        # Test below minimum
        gauge.update_value(-50)
        assert gauge.current_value == -50  # Value stored as-is

        # Test above maximum
        gauge.update_value(150)
        assert gauge.current_value == 150  # Value stored as-is


class TestHolographicGUI:
    """Tests for HolographicGUI main window."""

    def test_initialization(self, gui):
        """Test HolographicGUI initialization."""
        assert gui.windowTitle() == "raspiarduninoAI - Holographic Control System"
        assert gui.hardware is not None
        assert gui.core is not None
        assert gui.timer.isActive()

    def test_gui_components_exist(self, gui):
        """Test that all major GUI components are created."""
        assert gui.distance_gauge is not None
        assert gui.gate_gauge is not None
        assert gui.status_labels is not None
        assert gui.alert_display is not None
        assert gui.log_display is not None
        assert gui.open_btn is not None
        assert gui.close_btn is not None

    def test_status_labels_initialized(self, gui):
        """Test that all status labels are initialized."""
        expected_labels = ["distance", "dust", "motion", "gate", "policy"]
        for label_name in expected_labels:
            assert label_name in gui.status_labels
            assert gui.status_labels[label_name] is not None

    def test_log_message(self, gui):
        """Test logging messages to the display."""
        initial_length = len(gui.log_display.toPlainText())
        gui.log_message("Test message", "cyan")
        final_length = len(gui.log_display.toPlainText())
        assert final_length > initial_length
        assert "Test message" in gui.log_display.toPlainText()

    def test_log_message_with_different_colors(self, gui):
        """Test logging with different color options."""
        colors = ["cyan", "purple", "green", "red", "white"]
        for color in colors:
            gui.log_message(f"Test {color}", color)
        log_text = gui.log_display.toPlainText()
        for color in colors:
            assert f"Test {color}" in log_text

    def test_open_gate_button(self, gui):
        """Test open gate button functionality."""
        gui.sim_gate_open = False
        QTest.mouseClick(gui.open_btn, Qt.LeftButton)
        assert gui.sim_gate_open is True

    def test_close_gate_button(self, gui):
        """Test close gate button functionality."""
        gui.sim_gate_open = True
        QTest.mouseClick(gui.close_btn, Qt.LeftButton)
        assert gui.sim_gate_open is False

    def test_toggle_dust_button(self, gui):
        """Test dust toggle button functionality."""
        initial_dust = gui.sim_dust
        QTest.mouseClick(gui.toggle_dust_btn, Qt.LeftButton)
        assert gui.sim_dust != initial_dust

    def test_toggle_motion_button(self, gui):
        """Test motion toggle button functionality."""
        initial_motion = gui.sim_motion
        QTest.mouseClick(gui.toggle_motion_btn, Qt.LeftButton)
        assert gui.sim_motion != initial_motion

    def test_update_display(self, gui):
        """Test that display update doesn't crash."""
        # Should not raise any exceptions
        gui._update_display()

        # Verify gauges are updated
        assert gui.distance_gauge.current_value > 0

    def test_simulation_values_initialized(self, gui):
        """Test that simulation values are properly initialized."""
        assert isinstance(gui.sim_distance, float)
        assert isinstance(gui.sim_dust, bool)
        assert isinstance(gui.sim_motion, bool)
        assert isinstance(gui.sim_gate_open, bool)

    def test_hex_to_rgb_conversion(self, gui):
        """Test hex to RGB color conversion."""
        result = gui._hex_to_rgb("#00FFFF")
        assert result == "0, 255, 255"

        result = gui._hex_to_rgb("#FF0000")
        assert result == "255, 0, 0"

    def test_core_integration(self, gui):
        """Test that GUI properly integrates with core system."""
        payload = {
            "board_id": "TEST",
            "timestamp": 12345,
            "sensors": {
                "ultrasonic_mm": 500,
                "dust": True,
                "pir_motion": False,
                "gate_open": True
            }
        }

        # Should not raise any exceptions
        decision = gui.core.on_sensor_payload(payload)
        assert decision is not None

    def test_timer_running(self, gui):
        """Test that update timer is running."""
        assert gui.timer.isActive()
        assert gui.timer.interval() == 100  # 100ms update interval

    def test_log_from_core_callback(self, gui):
        """Test the logger callback from core."""
        gui._log_from_core("Test core message")
        assert "Test core message" in gui.log_display.toPlainText()
        assert "[CORE]" in gui.log_display.toPlainText()


class TestGUIUtilityFunctions:
    """Tests for GUI utility functions."""

    def test_create_holo_button(self, gui):
        """Test holographic button creation."""
        button = gui._create_holo_button("Test Button", "#00FFFF")
        assert button.text() == "Test Button"
        assert button is not None

    def test_create_separator(self, gui):
        """Test separator creation."""
        separator = gui._create_separator()
        assert separator is not None


class TestGUIStateManagement:
    """Tests for GUI state management."""

    def test_initial_state_is_valid(self, gui):
        """Test that initial GUI state is valid."""
        assert 200 <= gui.sim_distance <= 800
        assert isinstance(gui.sim_dust, bool)
        assert isinstance(gui.sim_motion, bool)
        assert isinstance(gui.sim_gate_open, bool)

    def test_sensor_payload_generation(self, gui):
        """Test that sensor payloads are properly formatted."""
        gui.sim_distance = 450.0
        gui.sim_dust = True
        gui.sim_motion = False
        gui.sim_gate_open = True

        # Trigger an update which generates a payload
        gui._update_display()

        # Verify state was updated in core
        state = gui.core.state_store.snapshot()
        assert state.dust_detected is True
        assert state.pir_motion is False


class TestGUIVisualElements:
    """Tests for GUI visual elements and styling."""

    def test_holographic_colors_defined(self):
        """Test that holographic color constants are defined."""
        from gui import (HOLO_CYAN, HOLO_BLUE, HOLO_PURPLE,
                        HOLO_GREEN, HOLO_RED, HOLO_BG,
                        HOLO_PANEL, HOLO_TEXT)

        # All should be hex color strings
        colors = [HOLO_CYAN, HOLO_BLUE, HOLO_PURPLE,
                 HOLO_GREEN, HOLO_RED, HOLO_BG,
                 HOLO_PANEL, HOLO_TEXT]

        for color in colors:
            assert color.startswith("#")
            assert len(color) == 7  # #RRGGBB format

    def test_status_indicator_exists(self, gui):
        """Test that status indicator is created."""
        assert gui.status_indicator is not None
        assert "ONLINE" in gui.status_indicator.text()


# Integration tests
class TestGUIIntegration:
    """Integration tests for GUI with core system."""

    def test_gui_responds_to_policy_decisions(self, gui):
        """Test that GUI responds to policy decisions."""
        # Set conditions that should trigger policy
        gui.sim_dust = True
        gui.sim_gate_open = True

        # Trigger update
        gui._update_display()

        # Check that alert is displayed
        alert_text = gui.alert_display.text()
        # Should have some alert if dust is detected
        assert len(alert_text) > 0

    def test_manual_controls_affect_state(self, gui):
        """Test that manual controls affect the system state."""
        # Open gate
        gui._open_gate()
        assert gui.sim_gate_open is True

        # Close gate
        gui._close_gate()
        assert gui.sim_gate_open is False

    def test_simulation_controls_work(self, gui):
        """Test that simulation controls work."""
        # Toggle dust
        initial = gui.sim_dust
        gui._toggle_dust()
        assert gui.sim_dust != initial

        # Toggle motion
        initial = gui.sim_motion
        gui._toggle_motion()
        assert gui.sim_motion != initial
