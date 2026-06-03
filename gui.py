#!/usr/bin/env python3
"""
Holographic GUI for raspiarduninoAI hopper control system.

Features:
- Futuristic holographic design with neon cyan/purple theme
- Real-time sensor monitoring with animated gauges
- Manual control interface
- Alert notifications
- System status indicators
"""

from __future__ import annotations

import sys
from typing import Optional
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QGridLayout, QTextEdit, QFrame
)
from PyQt5.QtCore import QTimer, Qt, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt5.QtGui import QPalette, QColor, QFont

import pyqtgraph as pg

from core import HopperCore, HardwareProtocol, build_default_core
from state import HopperState
from policies import PolicyConfig, PolicyEngine


# Holographic color scheme
HOLO_CYAN = "#00FFFF"
HOLO_BLUE = "#0080FF"
HOLO_PURPLE = "#8000FF"
HOLO_GREEN = "#00FF80"
HOLO_RED = "#FF0040"
HOLO_BG = "#0A0A1A"
HOLO_PANEL = "#151530"
HOLO_TEXT = "#E0E0FF"


class MockHardwareGUI:
    """Mock hardware implementation for GUI demonstration."""

    def __init__(self, gui: 'HolographicGUI'):
        self.gui = gui

    def send_gate(self, command: str) -> None:
        """Send command to gate controller."""
        self.gui.log_message(f"[GATE] Command sent: {command}", "cyan")

    def send_tele(self, command: str) -> None:
        """Send command to telescope controller."""
        self.gui.log_message(f"[TELE] Command sent: {command}", "purple")


class AnimatedLabel(QLabel):
    """Label with animated glow effect."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._glow_intensity = 0.5
        self.animation = QPropertyAnimation(self, b"glow_intensity")
        self.animation.setDuration(1500)
        self.animation.setStartValue(0.3)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.InOutSine)
        self.animation.setLoopCount(-1)  # Infinite loop

    @pyqtProperty(float)
    def glow_intensity(self):
        return self._glow_intensity

    @glow_intensity.setter
    def glow_intensity(self, value):
        self._glow_intensity = value
        self.update()

    def start_animation(self):
        """Start the glow animation."""
        self.animation.start()


class HolographicGauge(QWidget):
    """Circular gauge with holographic styling."""

    def __init__(self, title: str, min_val: float, max_val: float,
                 units: str = "", color: str = HOLO_CYAN, parent=None):
        super().__init__(parent)
        self.title = title
        self.min_val = min_val
        self.max_val = max_val
        self.units = units
        self.color = color
        self.current_value = 0.0

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Title
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 14px;
                font-weight: bold;
                background: transparent;
            }}
        """)
        layout.addWidget(title_label)

        # Create plot widget for gauge
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(HOLO_BG)
        self.plot_widget.hideAxis('bottom')
        self.plot_widget.hideAxis('left')
        self.plot_widget.setFixedSize(150, 150)

        # Configure gauge appearance
        self.plot_widget.setXRange(-1.2, 1.2)
        self.plot_widget.setYRange(-1.2, 1.2)
        self.plot_widget.setAspectLocked(True)

        # Create gauge elements
        self._create_gauge_elements()

        layout.addWidget(self.plot_widget, alignment=Qt.AlignCenter)

        # Value label
        self.value_label = QLabel("0.0 " + units)
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet(f"""
            QLabel {{
                color: {HOLO_TEXT};
                font-size: 16px;
                font-weight: bold;
                background: transparent;
            }}
        """)
        layout.addWidget(self.value_label)

        self.setLayout(layout)

    def _create_gauge_elements(self):
        """Create the visual elements of the gauge."""
        import numpy as np

        # Outer circle
        theta = np.linspace(0, 2 * np.pi, 100)
        x = np.cos(theta)
        y = np.sin(theta)
        self.plot_widget.plot(x, y, pen=pg.mkPen(self.color, width=2))

        # Inner circle
        x_inner = 0.8 * np.cos(theta)
        y_inner = 0.8 * np.sin(theta)
        self.plot_widget.plot(x_inner, y_inner, pen=pg.mkPen(self.color, width=1, style=Qt.DashLine))

        # Tick marks
        for i in range(12):
            angle = i * np.pi / 6
            x_start = 0.9 * np.cos(angle)
            y_start = 0.9 * np.sin(angle)
            x_end = 1.0 * np.cos(angle)
            y_end = 1.0 * np.sin(angle)
            self.plot_widget.plot([x_start, x_end], [y_start, y_end],
                                pen=pg.mkPen(self.color, width=2))

        # Needle (will be updated)
        self.needle = self.plot_widget.plot([0, 0], [0, 0.7],
                                           pen=pg.mkPen(HOLO_CYAN, width=3))

    def update_value(self, value: float):
        """Update the gauge value and needle position."""
        import numpy as np
        self.current_value = value
        self.value_label.setText(f"{value:.1f} {self.units}")

        # Calculate needle angle based on value
        normalized = (value - self.min_val) / (self.max_val - self.min_val)
        normalized = max(0, min(1, normalized))  # Clamp to 0-1
        angle = np.pi / 2 - (normalized * 1.5 * np.pi)  # -135° to +135°

        # Update needle position
        x_end = 0.7 * np.cos(angle)
        y_end = 0.7 * np.sin(angle)
        self.needle.setData([0, x_end], [0, y_end])


class HolographicGUI(QMainWindow):
    """Main holographic GUI window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("raspiarduninoAI - Holographic Control System")
        self.setGeometry(100, 100, 1200, 800)

        # Initialize hardware and core
        self.hardware = MockHardwareGUI(self)
        self.core = build_default_core(hardware=self.hardware, logger=self._log_from_core)

        # Setup UI
        self._setup_ui()
        self._apply_holographic_style()

        # Start update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_display)
        self.timer.start(100)  # Update every 100ms

        # Simulation data for demo
        self.sim_distance = 450.0
        self.sim_dust = False
        self.sim_motion = False
        self.sim_gate_open = True

    def _setup_ui(self):
        """Setup the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Header
        header = self._create_header()
        main_layout.addWidget(header)

        # Main content area
        content_layout = QHBoxLayout()

        # Left panel: Gauges
        gauges_panel = self._create_gauges_panel()
        content_layout.addWidget(gauges_panel, stretch=1)

        # Center panel: Status
        status_panel = self._create_status_panel()
        content_layout.addWidget(status_panel, stretch=2)

        # Right panel: Controls
        control_panel = self._create_control_panel()
        content_layout.addWidget(control_panel, stretch=1)

        main_layout.addLayout(content_layout)

        # Footer: Log
        log_panel = self._create_log_panel()
        main_layout.addWidget(log_panel)

        central_widget.setLayout(main_layout)

    def _create_header(self) -> QWidget:
        """Create the header with title and system status."""
        header = QFrame()
        header.setFrameStyle(QFrame.StyledPanel)
        layout = QHBoxLayout()

        # Title
        title = AnimatedLabel("◇ HOPPER CONTROL SYSTEM ◇")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            QLabel {{
                color: {HOLO_CYAN};
                font-size: 24px;
                font-weight: bold;
                padding: 10px;
                background: transparent;
            }}
        """)
        title.start_animation()
        layout.addWidget(title, stretch=1)

        # System status indicator
        self.status_indicator = QLabel("● ONLINE")
        self.status_indicator.setStyleSheet(f"""
            QLabel {{
                color: {HOLO_GREEN};
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                background: transparent;
            }}
        """)
        layout.addWidget(self.status_indicator)

        header.setLayout(layout)
        return header

    def _create_gauges_panel(self) -> QGroupBox:
        """Create the gauges panel with sensor displays."""
        group = QGroupBox("SENSOR TELEMETRY")
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Material level gauge
        self.distance_gauge = HolographicGauge(
            "MATERIAL LEVEL", 0, 1000, "mm", HOLO_CYAN
        )
        layout.addWidget(self.distance_gauge)

        # Gate position indicator
        self.gate_gauge = HolographicGauge(
            "GATE STATUS", 0, 1, "", HOLO_BLUE
        )
        layout.addWidget(self.gate_gauge)

        layout.addStretch()
        group.setLayout(layout)
        return group

    def _create_status_panel(self) -> QGroupBox:
        """Create the status display panel."""
        group = QGroupBox("SYSTEM STATUS")
        layout = QGridLayout()
        layout.setSpacing(10)

        # Sensor status indicators
        row = 0
        self.status_labels = {}

        for sensor_name, label_text in [
            ("distance", "Ultrasonic Distance"),
            ("dust", "Dust Sensor"),
            ("motion", "PIR Motion"),
            ("gate", "Gate Position"),
            ("policy", "Policy Status"),
        ]:
            label = QLabel(label_text + ":")
            label.setStyleSheet(f"color: {HOLO_TEXT}; font-size: 12px;")
            layout.addWidget(label, row, 0)

            value_label = QLabel("--")
            value_label.setStyleSheet(f"color: {HOLO_CYAN}; font-size: 12px; font-weight: bold;")
            layout.addWidget(value_label, row, 1)
            self.status_labels[sensor_name] = value_label
            row += 1

        # Alert display
        layout.addWidget(QLabel(), row, 0)  # Spacer
        row += 1

        alert_title = QLabel("ACTIVE ALERTS:")
        alert_title.setStyleSheet(f"color: {HOLO_RED}; font-size: 14px; font-weight: bold;")
        layout.addWidget(alert_title, row, 0, 1, 2)
        row += 1

        self.alert_display = QLabel("No active alerts")
        self.alert_display.setWordWrap(True)
        self.alert_display.setStyleSheet(f"""
            QLabel {{
                color: {HOLO_TEXT};
                font-size: 11px;
                padding: 10px;
                border: 1px solid {HOLO_CYAN};
                border-radius: 5px;
                background: rgba(0, 255, 255, 0.05);
            }}
        """)
        layout.addWidget(self.alert_display, row, 0, 1, 2)

        layout.setRowStretch(row + 1, 1)
        group.setLayout(layout)
        return group

    def _create_control_panel(self) -> QGroupBox:
        """Create the control panel with buttons."""
        group = QGroupBox("MANUAL CONTROLS")
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Gate controls
        gate_label = QLabel("Gate Control:")
        gate_label.setStyleSheet(f"color: {HOLO_TEXT}; font-size: 12px;")
        layout.addWidget(gate_label)

        self.open_btn = self._create_holo_button("OPEN GATE", HOLO_GREEN)
        self.open_btn.clicked.connect(self._open_gate)
        layout.addWidget(self.open_btn)

        self.close_btn = self._create_holo_button("CLOSE GATE", HOLO_RED)
        self.close_btn.clicked.connect(self._close_gate)
        layout.addWidget(self.close_btn)

        layout.addWidget(self._create_separator())

        # Simulation controls (for demo)
        sim_label = QLabel("Simulation:")
        sim_label.setStyleSheet(f"color: {HOLO_TEXT}; font-size: 12px;")
        layout.addWidget(sim_label)

        self.toggle_dust_btn = self._create_holo_button("TOGGLE DUST", HOLO_PURPLE)
        self.toggle_dust_btn.clicked.connect(self._toggle_dust)
        layout.addWidget(self.toggle_dust_btn)

        self.toggle_motion_btn = self._create_holo_button("TOGGLE MOTION", HOLO_PURPLE)
        self.toggle_motion_btn.clicked.connect(self._toggle_motion)
        layout.addWidget(self.toggle_motion_btn)

        layout.addStretch()
        group.setLayout(layout)
        return group

    def _create_log_panel(self) -> QGroupBox:
        """Create the log display panel."""
        group = QGroupBox("SYSTEM LOG")
        layout = QVBoxLayout()

        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(150)
        self.log_display.setStyleSheet(f"""
            QTextEdit {{
                background: {HOLO_BG};
                color: {HOLO_TEXT};
                border: 1px solid {HOLO_CYAN};
                border-radius: 5px;
                font-family: monospace;
                font-size: 10px;
                padding: 5px;
            }}
        """)
        layout.addWidget(self.log_display)

        group.setLayout(layout)
        return group

    def _create_holo_button(self, text: str, color: str) -> QPushButton:
        """Create a holographic-styled button."""
        button = QPushButton(text)
        button.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0, 0, 0, 0.3);
                color: {color};
                border: 2px solid {color};
                border-radius: 5px;
                padding: 10px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: rgba({self._hex_to_rgb(color)}, 0.2);
                border: 2px solid {color};
            }}
            QPushButton:pressed {{
                background: rgba({self._hex_to_rgb(color)}, 0.4);
            }}
        """)
        return button

    def _create_separator(self) -> QFrame:
        """Create a horizontal separator line."""
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"background: {HOLO_CYAN}; max-height: 2px;")
        return line

    def _hex_to_rgb(self, hex_color: str) -> str:
        """Convert hex color to RGB string."""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return f"{r}, {g}, {b}"

    def _apply_holographic_style(self):
        """Apply the holographic stylesheet to the window."""
        self.setStyleSheet(f"""
            QMainWindow {{
                background: {HOLO_BG};
            }}
            QWidget {{
                background: {HOLO_BG};
                color: {HOLO_TEXT};
            }}
            QGroupBox {{
                border: 2px solid {HOLO_CYAN};
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background: rgba(21, 21, 48, 0.6);
                font-weight: bold;
                color: {HOLO_CYAN};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
                color: {HOLO_CYAN};
            }}
            QFrame {{
                border: 1px solid {HOLO_CYAN};
                border-radius: 5px;
                background: rgba(21, 21, 48, 0.4);
            }}
        """)

    def _update_display(self):
        """Update the display with current sensor data."""
        # Simulate sensor data changes
        import random
        self.sim_distance += random.uniform(-5, 5)
        self.sim_distance = max(200, min(800, self.sim_distance))

        # Create sensor payload
        payload = {
            "board_id": "GATE_001",
            "timestamp": int(datetime.now().timestamp() * 1000),
            "sensors": {
                "ultrasonic_mm": int(self.sim_distance),
                "dust": self.sim_dust,
                "pir_motion": self.sim_motion,
                "gate_open": self.sim_gate_open
            }
        }

        # Process through core
        decision = self.core.on_sensor_payload(payload)

        # Update gauges
        self.distance_gauge.update_value(self.sim_distance)
        self.gate_gauge.update_value(1.0 if self.sim_gate_open else 0.0)

        # Update status labels
        state = self.core.state_store.snapshot()
        self.status_labels["distance"].setText(f"{state.ultrasonic_mm} mm" if state.ultrasonic_mm else "--")
        self.status_labels["dust"].setText("DETECTED" if state.dust_detected else "Clear")
        self.status_labels["motion"].setText("DETECTED" if state.pir_motion else "None")
        self.status_labels["gate"].setText("OPEN" if state.gate_open else "CLOSED")

        # Update dust/motion status colors
        self.status_labels["dust"].setStyleSheet(
            f"color: {HOLO_RED if state.dust_detected else HOLO_GREEN}; font-size: 12px; font-weight: bold;"
        )
        self.status_labels["motion"].setStyleSheet(
            f"color: {HOLO_RED if state.pir_motion else HOLO_GREEN}; font-size: 12px; font-weight: bold;"
        )

        # Update policy status
        if decision.reasons:
            self.status_labels["policy"].setText(f"Active ({len(decision.reasons)} conditions)")
            self.status_labels["policy"].setStyleSheet(f"color: {HOLO_RED}; font-size: 12px; font-weight: bold;")
        else:
            self.status_labels["policy"].setText("Normal")
            self.status_labels["policy"].setStyleSheet(f"color: {HOLO_GREEN}; font-size: 12px; font-weight: bold;")

        # Update alerts
        if decision.alert:
            self.alert_display.setText(f"⚠ {decision.alert}")
            self.alert_display.setStyleSheet(f"""
                QLabel {{
                    color: {HOLO_RED};
                    font-size: 11px;
                    padding: 10px;
                    border: 2px solid {HOLO_RED};
                    border-radius: 5px;
                    background: rgba(255, 0, 64, 0.1);
                    font-weight: bold;
                }}
            """)
        else:
            self.alert_display.setText("✓ No active alerts - System nominal")
            self.alert_display.setStyleSheet(f"""
                QLabel {{
                    color: {HOLO_GREEN};
                    font-size: 11px;
                    padding: 10px;
                    border: 1px solid {HOLO_CYAN};
                    border-radius: 5px;
                    background: rgba(0, 255, 255, 0.05);
                }}
            """)

    def _open_gate(self):
        """Manually open the gate."""
        self.sim_gate_open = True
        self.log_message("[USER] Manual gate open command", "green")
        self.hardware.send_gate("OPEN")

    def _close_gate(self):
        """Manually close the gate."""
        self.sim_gate_open = False
        self.log_message("[USER] Manual gate close command", "red")
        self.hardware.send_gate("CLOSE")

    def _toggle_dust(self):
        """Toggle dust detection for simulation."""
        self.sim_dust = not self.sim_dust
        status = "ON" if self.sim_dust else "OFF"
        self.log_message(f"[SIM] Dust sensor: {status}", "purple")

    def _toggle_motion(self):
        """Toggle motion detection for simulation."""
        self.sim_motion = not self.sim_motion
        status = "ON" if self.sim_motion else "OFF"
        self.log_message(f"[SIM] Motion sensor: {status}", "purple")

    def log_message(self, message: str, color: str = "white"):
        """Add a message to the log display."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        color_map = {
            "cyan": HOLO_CYAN,
            "purple": HOLO_PURPLE,
            "green": HOLO_GREEN,
            "red": HOLO_RED,
            "white": HOLO_TEXT
        }
        hex_color = color_map.get(color, HOLO_TEXT)

        self.log_display.append(
            f'<span style="color: {hex_color}">[{timestamp}] {message}</span>'
        )

        # Auto-scroll to bottom
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _log_from_core(self, message: str):
        """Logger callback from core system."""
        self.log_message(f"[CORE] {message}", "cyan")


def main():
    """Main entry point for the holographic GUI."""
    app = QApplication(sys.argv)

    # Set application-wide font
    font = QFont("Consolas", 10)
    app.setFont(font)

    # Create and show the GUI
    gui = HolographicGUI()
    gui.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
