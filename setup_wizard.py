#!/usr/bin/env python3
"""
Setup Wizard for raspiarduninoAI.

Provides user-friendly interface for:
- Initial system configuration
- Motor setup (4x NEMA 17)
- Sensor calibration
- Visual feedback
"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
    QPushButton, QGroupBox, QSlider, QProgressBar, QTextEdit, QTabWidget,
    QWidget, QInputDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QPalette, QColor

from config import SystemConfig, MotorConfig, SensorConfig, UltrasonicSensorConfig, ConfigManager

# Holographic colors
HOLO_CYAN = "#00FFFF"
HOLO_PURPLE = "#8000FF"
HOLO_GREEN = "#00FF80"
HOLO_BG = "#0A0A1A"
HOLO_TEXT = "#E0E0FF"


class WelcomePage(QWizardPage):
    """Welcome page of the setup wizard."""

    def __init__(self):
        super().__init__()
        self.setTitle("Welcome to raspiarduninoAI Setup")
        self.setSubTitle("This wizard will help you configure your hopper control system")

        layout = QVBoxLayout()

        intro = QLabel(
            "This setup wizard will guide you through:\n\n"
            "• Motor configuration (NEMA 17 steppers)\n"
            "• Sensor setup and calibration\n"
            "• System preferences\n"
            "• Advanced settings (optional)\n\n"
            "You can always change these settings later from the\n"
            "Advanced Settings menu."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # System name
        form = QFormLayout()
        self.system_name = QLineEdit("raspiarduninoAI")
        self.location = QLineEdit("Lab")
        form.addRow("System Name:", self.system_name)
        form.addRow("Location:", self.location)
        layout.addLayout(form)

        layout.addStretch()
        self.setLayout(layout)

        # Register fields
        self.registerField("system_name*", self.system_name)
        self.registerField("location", self.location)


class MotorConfigPage(QWizardPage):
    """Motor configuration page."""

    def __init__(self):
        super().__init__()
        self.setTitle("Motor Configuration")
        self.setSubTitle("Configure your NEMA 17 stepper motors")

        layout = QVBoxLayout()

        # Tab widget for multiple motors
        self.motor_tabs = QTabWidget()

        # Create 4 motor configuration tabs
        self.motor_configs = []
        for i in range(4):
            motor_widget = self._create_motor_config(i)
            self.motor_configs.append(motor_widget)
            self.motor_tabs.addTab(motor_widget, f"Motor {i+1}")

        layout.addWidget(self.motor_tabs)

        # Run all together checkbox
        self.run_all_together = QCheckBox("Run all motors together (synchronized)")
        layout.addWidget(self.run_all_together)

        self.setLayout(layout)

    def _create_motor_config(self, index: int) -> QWidget:
        """Create configuration widget for a single motor."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Enable/disable
        enabled_cb = QCheckBox("Enable this motor")
        enabled_cb.setChecked(index < 2)  # First two enabled by default
        layout.addWidget(enabled_cb)

        # Motor settings
        form = QFormLayout()

        name_edit = QLineEdit(f"Motor {index+1}")
        form.addRow("Name:", name_edit)

        steps_spin = QSpinBox()
        steps_spin.setRange(100, 400)
        steps_spin.setValue(200)
        steps_spin.setSuffix(" steps/rev")
        form.addRow("Steps per Revolution:", steps_spin)

        microsteps_combo = QComboBox()
        microsteps_combo.addItems(["1", "2", "4", "8", "16", "32"])
        microsteps_combo.setCurrentText("16")
        form.addRow("Microstepping:", microsteps_combo)

        speed_spin = QSpinBox()
        speed_spin.setRange(1, 300)
        speed_spin.setValue(60)
        speed_spin.setSuffix(" RPM")
        form.addRow("Max Speed:", speed_spin)

        accel_spin = QSpinBox()
        accel_spin.setRange(100, 2000)
        accel_spin.setValue(500)
        accel_spin.setSuffix(" steps/s²")
        form.addRow("Acceleration:", accel_spin)

        current_spin = QSpinBox()
        current_spin.setRange(100, 2000)
        current_spin.setValue(1000)
        current_spin.setSuffix(" mA")
        form.addRow("Current:", current_spin)

        inverted_cb = QCheckBox("Invert direction")
        form.addRow("Direction:", inverted_cb)

        layout.addLayout(form)

        # Steps per minute display
        spm_label = QLabel("Steps/min: 192000")
        spm_label.setStyleSheet(f"color: {HOLO_CYAN}; font-weight: bold;")

        def update_spm():
            steps = steps_spin.value()
            microsteps = int(microsteps_combo.currentText())
            rpm = speed_spin.value()
            spm = steps * microsteps * rpm
            spm_label.setText(f"Steps/min: {spm:,}")

        steps_spin.valueChanged.connect(update_spm)
        microsteps_combo.currentTextChanged.connect(update_spm)
        speed_spin.valueChanged.connect(update_spm)

        layout.addWidget(spm_label)
        layout.addStretch()

        widget.setLayout(layout)

        # Store references
        widget.enabled_cb = enabled_cb
        widget.name_edit = name_edit
        widget.steps_spin = steps_spin
        widget.microsteps_combo = microsteps_combo
        widget.speed_spin = speed_spin
        widget.accel_spin = accel_spin
        widget.current_spin = current_spin
        widget.inverted_cb = inverted_cb

        return widget

    def get_motor_configs(self) -> list[MotorConfig]:
        """Get motor configurations from the wizard."""
        configs = []
        for widget in self.motor_configs:
            config = MotorConfig(
                name=widget.name_edit.text(),
                enabled=widget.enabled_cb.isChecked(),
                steps_per_revolution=widget.steps_spin.value(),
                microsteps=int(widget.microsteps_combo.currentText()),
                max_speed_rpm=widget.speed_spin.value(),
                acceleration=widget.accel_spin.value(),
                current_ma=widget.current_spin.value(),
                inverted=widget.inverted_cb.isChecked(),
            )
            configs.append(config)
        return configs


class SensorConfigPage(QWizardPage):
    """Sensor configuration page."""

    def __init__(self):
        super().__init__()
        self.setTitle("Sensor Configuration")
        self.setSubTitle("Configure sensors and their sensitivity")

        layout = QVBoxLayout()

        # Ultrasonic sensor
        ultrasonic_group = self._create_ultrasonic_config()
        layout.addWidget(ultrasonic_group)

        # Other sensors
        other_group = self._create_other_sensors_config()
        layout.addWidget(other_group)

        layout.addStretch()
        self.setLayout(layout)

    def _create_ultrasonic_config(self) -> QGroupBox:
        """Create ultrasonic sensor configuration."""
        group = QGroupBox("Ultrasonic Distance Sensor (Material Level)")
        layout = QVBoxLayout()

        form = QFormLayout()

        self.ultra_name = QLineEdit("Material Level")
        form.addRow("Sensor Name:", self.ultra_name)

        self.ultra_trigger = QSpinBox()
        self.ultra_trigger.setRange(0, 2000)
        self.ultra_trigger.setValue(600)
        self.ultra_trigger.setSuffix(" mm")
        form.addRow("Low Material Threshold:", self.ultra_trigger)

        self.ultra_freq = QSpinBox()
        self.ultra_freq.setRange(1, 50)
        self.ultra_freq.setValue(10)
        self.ultra_freq.setSuffix(" Hz")
        form.addRow("Update Frequency:", self.ultra_freq)

        layout.addLayout(form)

        # Visualization options
        self.ultra_show_beam = QCheckBox("Show beam visualization")
        self.ultra_show_beam.setChecked(True)
        layout.addWidget(self.ultra_show_beam)

        self.ultra_show_numeric = QCheckBox("Show numeric distance")
        self.ultra_show_numeric.setChecked(True)
        layout.addWidget(self.ultra_show_numeric)

        # Sensitivity slider
        sens_layout = QHBoxLayout()
        sens_layout.addWidget(QLabel("Sensitivity:"))
        self.ultra_sensitivity = QSlider(Qt.Horizontal)
        self.ultra_sensitivity.setRange(0, 100)
        self.ultra_sensitivity.setValue(50)
        sens_layout.addWidget(self.ultra_sensitivity)
        self.ultra_sens_label = QLabel("50%")

        def update_sens(val):
            self.ultra_sens_label.setText(f"{val}%")

        self.ultra_sensitivity.valueChanged.connect(update_sens)
        sens_layout.addWidget(self.ultra_sens_label)
        layout.addLayout(sens_layout)

        group.setLayout(layout)
        return group

    def _create_other_sensors_config(self) -> QGroupBox:
        """Create other sensors configuration."""
        group = QGroupBox("Other Sensors")
        layout = QVBoxLayout()

        # Dust sensor
        dust_layout = QHBoxLayout()
        self.dust_enabled = QCheckBox("Dust Sensor")
        self.dust_enabled.setChecked(True)
        dust_layout.addWidget(self.dust_enabled)
        dust_layout.addWidget(QLabel("Sensitivity:"))
        self.dust_sensitivity = QSlider(Qt.Horizontal)
        self.dust_sensitivity.setRange(0, 100)
        self.dust_sensitivity.setValue(50)
        dust_layout.addWidget(self.dust_sensitivity)
        layout.addLayout(dust_layout)

        # PIR sensor
        pir_layout = QHBoxLayout()
        self.pir_enabled = QCheckBox("PIR Motion Sensor")
        self.pir_enabled.setChecked(True)
        pir_layout.addWidget(self.pir_enabled)
        pir_layout.addWidget(QLabel("Sensitivity:"))
        self.pir_sensitivity = QSlider(Qt.Horizontal)
        self.pir_sensitivity.setRange(0, 100)
        self.pir_sensitivity.setValue(50)
        pir_layout.addWidget(self.pir_sensitivity)
        layout.addLayout(pir_layout)

        # Gate position sensor
        gate_layout = QHBoxLayout()
        self.gate_enabled = QCheckBox("Gate Position Sensor")
        self.gate_enabled.setChecked(True)
        gate_layout.addWidget(self.gate_enabled)
        layout.addLayout(gate_layout)

        group.setLayout(layout)
        return group

    def get_sensor_configs(self) -> list[SensorConfig]:
        """Get sensor configurations from the wizard."""
        configs = []

        # Ultrasonic
        ultra = UltrasonicSensorConfig(
            name=self.ultra_name.text(),
            enabled=True,
            update_frequency_hz=self.ultra_freq.value(),
            sensitivity=self.ultra_sensitivity.value(),
            trigger_distance_mm=self.ultra_trigger.value(),
            show_beam_visualization=self.ultra_show_beam.isChecked(),
            show_numeric=self.ultra_show_numeric.isChecked(),
        )
        configs.append(ultra)

        # Dust
        if self.dust_enabled.isChecked():
            dust = SensorConfig(
                name="Dust Sensor",
                enabled=True,
                sensor_type="dust",
                sensitivity=self.dust_sensitivity.value(),
            )
            configs.append(dust)

        # PIR
        if self.pir_enabled.isChecked():
            pir = SensorConfig(
                name="PIR Motion",
                enabled=True,
                sensor_type="pir",
                sensitivity=self.pir_sensitivity.value(),
            )
            configs.append(pir)

        # Gate
        if self.gate_enabled.isChecked():
            gate = SensorConfig(
                name="Gate Position",
                enabled=True,
                sensor_type="limit_switch",
            )
            configs.append(gate)

        return configs


class CompletionPage(QWizardPage):
    """Final page showing configuration summary."""

    def __init__(self):
        super().__init__()
        self.setTitle("Configuration Complete")
        self.setSubTitle("Review your settings")

        layout = QVBoxLayout()

        summary_label = QLabel("Your system has been configured successfully!")
        summary_label.setStyleSheet(f"color: {HOLO_GREEN}; font-weight: bold; font-size: 14px;")
        layout.addWidget(summary_label)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        layout.addWidget(self.summary_text)

        # Set password checkbox
        self.set_password_cb = QCheckBox("Set master password for advanced settings")
        layout.addWidget(self.set_password_cb)

        self.setLayout(layout)

    def initializePage(self):
        """Called when page is shown - populate summary."""
        wizard = self.wizard()

        summary = []
        summary.append("=== System Configuration ===\n")
        summary.append(f"System Name: {wizard.field('system_name')}")
        summary.append(f"Location: {wizard.field('location')}\n")

        summary.append("=== Motors ===")
        motor_page = wizard.page(1)
        for i, config in enumerate(motor_page.get_motor_configs(), 1):
            if config.enabled:
                summary.append(f"{i}. {config.name}: {config.steps_per_minute:,} steps/min")

        summary.append("\n=== Sensors ===")
        sensor_page = wizard.page(2)
        for config in sensor_page.get_sensor_configs():
            summary.append(f"• {config.name} (sensitivity: {config.sensitivity}%)")

        self.summary_text.setText("\n".join(summary))


class SetupWizard(QWizard):
    """Main setup wizard dialog."""

    config_complete = pyqtSignal(SystemConfig)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("raspiarduninoAI Setup Wizard")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setMinimumSize(800, 600)

        # Add pages
        self.addPage(WelcomePage())
        self.addPage(MotorConfigPage())
        self.addPage(SensorConfigPage())
        self.addPage(CompletionPage())

        # Apply holographic style
        self._apply_style()

        # Connect finish button
        self.finished.connect(self._on_finished)

    def _apply_style(self):
        """Apply holographic styling."""
        self.setStyleSheet(f"""
            QWizard {{
                background: {HOLO_BG};
                color: {HOLO_TEXT};
            }}
            QWizardPage {{
                background: {HOLO_BG};
                color: {HOLO_TEXT};
            }}
            QLabel {{
                color: {HOLO_TEXT};
            }}
            QGroupBox {{
                border: 2px solid {HOLO_CYAN};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                color: {HOLO_CYAN};
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            QPushButton {{
                background: rgba(0, 255, 255, 0.2);
                border: 2px solid {HOLO_CYAN};
                color: {HOLO_CYAN};
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: rgba(0, 255, 255, 0.3);
            }}
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
                background: rgba(21, 21, 48, 0.6);
                border: 1px solid {HOLO_CYAN};
                color: {HOLO_TEXT};
                padding: 4px;
                border-radius: 3px;
            }}
            QTextEdit {{
                background: rgba(21, 21, 48, 0.6);
                border: 1px solid {HOLO_CYAN};
                color: {HOLO_TEXT};
                padding: 8px;
                border-radius: 3px;
            }}
            QCheckBox {{
                color: {HOLO_TEXT};
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {HOLO_CYAN};
                border-radius: 3px;
                background: rgba(21, 21, 48, 0.6);
            }}
            QCheckBox::indicator:checked {{
                background: {HOLO_CYAN};
            }}
            QSlider::groove:horizontal {{
                height: 8px;
                background: rgba(21, 21, 48, 0.6);
                border: 1px solid {HOLO_CYAN};
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: {HOLO_CYAN};
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }}
            QTabWidget::pane {{
                border: 2px solid {HOLO_CYAN};
                border-radius: 5px;
            }}
            QTabBar::tab {{
                background: rgba(21, 21, 48, 0.6);
                border: 1px solid {HOLO_CYAN};
                color: {HOLO_TEXT};
                padding: 8px 16px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: rgba(0, 255, 255, 0.2);
                border-bottom: 3px solid {HOLO_CYAN};
            }}
        """)

    def _on_finished(self, result):
        """Handle wizard completion."""
        if result == QWizard.Accepted:
            # Create configuration from wizard data
            config = SystemConfig()

            # System info
            config.system_name = self.field('system_name')
            config.location = self.field('location')

            # Motors
            motor_page = self.page(1)
            config.motors = motor_page.get_motor_configs()

            # Sensors
            sensor_page = self.page(2)
            config.sensors = sensor_page.get_sensor_configs()

            # Password
            completion_page = self.page(3)
            if completion_page.set_password_cb.isChecked():
                password, ok = QInputDialog.getText(
                    self, "Set Master Password",
                    "Enter master password for advanced settings:",
                    QLineEdit.Password
                )
                if ok and password:
                    config.set_password(password)

            # Emit signal with completed configuration
            self.config_complete.emit(config)
