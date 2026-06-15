#!/usr/bin/env python3
"""
Advanced Settings Dialog for raspiarduninoAI.

Camera-style menu navigation with holographic theme.
"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QListWidget, QListWidgetItem, QWidget,
    QSpinBox, QDoubleSpinBox, QCheckBox, QLineEdit, QGroupBox,
    QGridLayout, QSlider, QComboBox, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from config import SystemConfig, MotorConfig, SensorConfig, PowerConfig


# Holographic color scheme
HOLO_CYAN = "#00FFFF"
HOLO_BLUE = "#0080FF"
HOLO_PURPLE = "#8000FF"
HOLO_GREEN = "#00FF80"
HOLO_RED = "#FF0040"
HOLO_BG = "#0A0A1A"
HOLO_PANEL = "#151530"
HOLO_TEXT = "#E0E0FF"


class AdvancedSettingsDialog(QDialog):
    """Advanced settings dialog with camera-style menu navigation."""

    config_changed = pyqtSignal(SystemConfig)

    def __init__(self, config: SystemConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Advanced Settings")
        self.setMinimumSize(900, 600)
        self._setup_ui()
        self._apply_style()

    def _setup_ui(self):
        """Create the UI layout."""
        layout = QHBoxLayout(self)

        # Left side: Menu navigation
        self.menu_list = QListWidget()
        self.menu_list.setMaximumWidth(250)
        self.menu_list.currentRowChanged.connect(self._on_menu_changed)

        # Add menu items
        menu_items = [
            "⚙️ System",
            "🔧 Motors",
            "📡 Sensors",
            "⚡ Power",
            "🎨 UI Settings",
            "🔌 Communication",
        ]
        for item_text in menu_items:
            item = QListWidgetItem(item_text)
            self.menu_list.addItem(item)

        # Right side: Stacked pages
        self.pages = QStackedWidget()

        # Create pages
        self.pages.addWidget(self._scrollable(self._create_system_page()))
        self.pages.addWidget(self._scrollable(self._create_motors_page()))
        self.pages.addWidget(self._scrollable(self._create_sensors_page()))
        self.pages.addWidget(self._scrollable(self._create_power_page()))
        self.pages.addWidget(self._scrollable(self._create_ui_page()))
        self.pages.addWidget(self._scrollable(self._create_communication_page()))

        # Add to layout
        layout.addWidget(self.menu_list)
        layout.addWidget(self.pages, 1)

        # Bottom buttons
        button_layout = QHBoxLayout()

        self.save_btn = QPushButton("💾 Save")
        self.save_btn.clicked.connect(self.accept)

        self.cancel_btn = QPushButton("❌ Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)

        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(button_layout)

        widget = QWidget()
        widget.setLayout(main_layout)

        outer_layout = QVBoxLayout(self)
        outer_layout.addWidget(widget)

    def _scrollable(self, page: QWidget) -> QScrollArea:
        """Wrap a settings page in a vertical scroll area."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        return scroll

        """Create system settings page."""
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("⚙️ System Settings")
        title.setStyleSheet(f"font-size: 24px; color: {HOLO_CYAN}; font-weight: bold;")
        layout.addWidget(title)

        # System name
        group = QGroupBox("System Identification")
        group_layout = QGridLayout()

        group_layout.addWidget(QLabel("System Name:"), 0, 0)
        self.system_name_edit = QLineEdit(self.config.system_name)
        group_layout.addWidget(self.system_name_edit, 0, 1)

        group_layout.addWidget(QLabel("Location:"), 1, 0)
        self.location_edit = QLineEdit(self.config.location)
        group_layout.addWidget(self.location_edit, 1, 1)

        group.setLayout(group_layout)
        layout.addWidget(group)

        layout.addStretch()
        return page

    def _create_motors_page(self) -> QWidget:
        """Create motor configuration page."""
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("🔧 Motor Configuration")
        title.setStyleSheet(f"font-size: 24px; color: {HOLO_CYAN}; font-weight: bold;")
        layout.addWidget(title)

        self.motor_widgets = []

        for i, motor in enumerate(self.config.motors):
            group = QGroupBox(f"Motor {i+1}: {motor.name}")
            group_layout = QGridLayout()

            row = 0

            # Enabled
            enabled_cb = QCheckBox("Enabled")
            enabled_cb.setChecked(motor.enabled)
            group_layout.addWidget(enabled_cb, row, 0, 1, 2)
            row += 1

            # Name
            group_layout.addWidget(QLabel("Name:"), row, 0)
            name_edit = QLineEdit(motor.name)
            group_layout.addWidget(name_edit, row, 1)
            row += 1

            # Steps per revolution
            group_layout.addWidget(QLabel("Steps/Rev:"), row, 0)
            steps_spin = QSpinBox()
            steps_spin.setRange(100, 400)
            steps_spin.setValue(motor.steps_per_revolution)
            group_layout.addWidget(steps_spin, row, 1)
            row += 1

            # Microsteps
            group_layout.addWidget(QLabel("Microsteps:"), row, 0)
            microsteps_combo = QComboBox()
            microsteps_combo.addItems(["1", "2", "4", "8", "16", "32"])
            microsteps_combo.setCurrentText(str(motor.microsteps))
            group_layout.addWidget(microsteps_combo, row, 1)
            row += 1

            # Max speed
            group_layout.addWidget(QLabel("Max Speed (RPM):"), row, 0)
            speed_spin = QSpinBox()
            speed_spin.setRange(1, 500)
            speed_spin.setValue(motor.max_speed_rpm)
            group_layout.addWidget(speed_spin, row, 1)
            row += 1

            # Acceleration
            group_layout.addWidget(QLabel("Acceleration:"), row, 0)
            accel_spin = QSpinBox()
            accel_spin.setRange(100, 2000)
            accel_spin.setValue(motor.acceleration)
            group_layout.addWidget(accel_spin, row, 1)
            row += 1

            # Current
            group_layout.addWidget(QLabel("Current (mA):"), row, 0)
            current_spin = QSpinBox()
            current_spin.setRange(100, 2000)
            current_spin.setValue(motor.current_ma)
            group_layout.addWidget(current_spin, row, 1)
            row += 1

            # Inverted
            inverted_cb = QCheckBox("Inverted Direction")
            inverted_cb.setChecked(motor.inverted)
            group_layout.addWidget(inverted_cb, row, 0, 1, 2)

            group.setLayout(group_layout)
            layout.addWidget(group)

            self.motor_widgets.append({
                'enabled': enabled_cb,
                'name': name_edit,
                'steps_per_revolution': steps_spin,
                'microsteps': microsteps_combo,
                'max_speed_rpm': speed_spin,
                'acceleration': accel_spin,
                'current_ma': current_spin,
                'inverted': inverted_cb,
            })

        layout.addStretch()
        return page

    def _create_sensors_page(self) -> QWidget:
        """Create sensor configuration page."""
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("📡 Sensor Configuration")
        title.setStyleSheet(f"font-size: 24px; color: {HOLO_CYAN}; font-weight: bold;")
        layout.addWidget(title)

        self.sensor_widgets = []

        for i, sensor in enumerate(self.config.sensors):
            group = QGroupBox(f"Sensor {i+1}: {sensor.name}")
            group_layout = QGridLayout()

            row = 0

            # Enabled
            enabled_cb = QCheckBox("Enabled")
            enabled_cb.setChecked(sensor.enabled)
            group_layout.addWidget(enabled_cb, row, 0, 1, 2)
            row += 1

            # Name
            group_layout.addWidget(QLabel("Name:"), row, 0)
            name_edit = QLineEdit(sensor.name)
            group_layout.addWidget(name_edit, row, 1)
            row += 1

            # Sensitivity
            group_layout.addWidget(QLabel("Sensitivity (%):"), row, 0)
            sensitivity_slider = QSlider(Qt.Horizontal)
            sensitivity_slider.setRange(0, 100)
            sensitivity_slider.setValue(sensor.sensitivity)
            sensitivity_label = QLabel(f"{sensor.sensitivity}%")
            sensitivity_slider.valueChanged.connect(
                lambda v, lbl=sensitivity_label: lbl.setText(f"{v}%")
            )
            group_layout.addWidget(sensitivity_slider, row, 1)
            group_layout.addWidget(sensitivity_label, row, 2)
            row += 1

            # Update frequency
            group_layout.addWidget(QLabel("Update Freq (Hz):"), row, 0)
            freq_spin = QSpinBox()
            freq_spin.setRange(1, 100)
            freq_spin.setValue(sensor.update_frequency_hz)
            group_layout.addWidget(freq_spin, row, 1)
            row += 1

            # Show visual
            visual_cb = QCheckBox("Show Visual Feedback")
            visual_cb.setChecked(sensor.show_visual)
            group_layout.addWidget(visual_cb, row, 0, 1, 2)
            row += 1

            # Show numeric
            numeric_cb = QCheckBox("Show Numeric Value")
            numeric_cb.setChecked(sensor.show_numeric)
            group_layout.addWidget(numeric_cb, row, 0, 1, 2)

            group.setLayout(group_layout)
            layout.addWidget(group)

            self.sensor_widgets.append({
                'enabled': enabled_cb,
                'name': name_edit,
                'sensitivity': sensitivity_slider,
                'update_frequency_hz': freq_spin,
                'show_visual': visual_cb,
                'show_numeric': numeric_cb,
            })

        layout.addStretch()
        return page

    def _create_power_page(self) -> QWidget:
        """Create power monitoring page."""
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("⚡ Power Monitoring")
        title.setStyleSheet(f"font-size: 24px; color: {HOLO_CYAN}; font-weight: bold;")
        layout.addWidget(title)

        group = QGroupBox("Power Monitoring Settings")
        group_layout = QGridLayout()

        # Monitor voltage
        self.monitor_voltage_cb = QCheckBox("Monitor Voltage")
        self.monitor_voltage_cb.setChecked(self.config.power.monitor_voltage)
        group_layout.addWidget(self.monitor_voltage_cb, 0, 0, 1, 2)

        # Voltage warning
        group_layout.addWidget(QLabel("Voltage Warning (V):"), 1, 0)
        self.voltage_warning_spin = QDoubleSpinBox()
        self.voltage_warning_spin.setRange(5.0, 30.0)
        self.voltage_warning_spin.setSingleStep(0.1)
        self.voltage_warning_spin.setValue(self.config.power.voltage_warning_v)
        group_layout.addWidget(self.voltage_warning_spin, 1, 1)

        # Monitor current
        self.monitor_current_cb = QCheckBox("Monitor Current")
        self.monitor_current_cb.setChecked(self.config.power.monitor_current)
        group_layout.addWidget(self.monitor_current_cb, 2, 0, 1, 2)

        # Current warning
        group_layout.addWidget(QLabel("Current Warning (A):"), 3, 0)
        self.current_warning_spin = QDoubleSpinBox()
        self.current_warning_spin.setRange(0.1, 20.0)
        self.current_warning_spin.setSingleStep(0.1)
        self.current_warning_spin.setValue(self.config.power.current_warning_a)
        group_layout.addWidget(self.current_warning_spin, 3, 1)

        group.setLayout(group_layout)
        layout.addWidget(group)

        layout.addStretch()
        return page

    def _create_ui_page(self) -> QWidget:
        """Create UI settings page."""
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("🎨 UI Settings")
        title.setStyleSheet(f"font-size: 24px; color: {HOLO_CYAN}; font-weight: bold;")
        layout.addWidget(title)

        group = QGroupBox("User Interface")
        group_layout = QGridLayout()

        # Window title
        group_layout.addWidget(QLabel("Window Title:"), 0, 0)
        self.window_title_edit = QLineEdit(self.config.window_title)
        group_layout.addWidget(self.window_title_edit, 0, 1)

        # Theme
        group_layout.addWidget(QLabel("Theme:"), 1, 0)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["holographic", "classic", "minimal"])
        self.theme_combo.setCurrentText(self.config.ui_theme)
        group_layout.addWidget(self.theme_combo, 1, 1)

        # Show advanced controls
        self.show_advanced_cb = QCheckBox("Show Advanced Controls")
        self.show_advanced_cb.setChecked(self.config.show_advanced_controls)
        group_layout.addWidget(self.show_advanced_cb, 2, 0, 1, 2)

        group.setLayout(group_layout)
        layout.addWidget(group)

        layout.addStretch()
        return page

    def _create_communication_page(self) -> QWidget:
        """Create communication settings page."""
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("🔌 Communication Settings")
        title.setStyleSheet(f"font-size: 24px; color: {HOLO_CYAN}; font-weight: bold;")
        layout.addWidget(title)

        group = QGroupBox("Serial Communication")
        group_layout = QGridLayout()

        # Timeout
        group_layout.addWidget(QLabel("Serial Timeout (s):"), 0, 0)
        self.serial_timeout_spin = QDoubleSpinBox()
        self.serial_timeout_spin.setRange(0.1, 10.0)
        self.serial_timeout_spin.setSingleStep(0.1)
        self.serial_timeout_spin.setValue(self.config.serial_timeout_s)
        group_layout.addWidget(self.serial_timeout_spin, 0, 1)

        # Reconnect attempts
        group_layout.addWidget(QLabel("Reconnect Attempts:"), 1, 0)
        self.reconnect_spin = QSpinBox()
        self.reconnect_spin.setRange(0, 10)
        self.reconnect_spin.setValue(self.config.reconnect_attempts)
        group_layout.addWidget(self.reconnect_spin, 1, 1)

        group.setLayout(group_layout)
        layout.addWidget(group)

        layout.addStretch()
        return page

    def _on_menu_changed(self, index: int):
        """Handle menu selection change."""
        self.pages.setCurrentIndex(index)

    def _apply_style(self):
        """Apply holographic styling."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {HOLO_BG};
                color: {HOLO_TEXT};
            }}
            QListWidget {{
                background-color: {HOLO_PANEL};
                color: {HOLO_TEXT};
                border: 2px solid {HOLO_CYAN};
                border-radius: 5px;
                font-size: 14px;
                padding: 5px;
            }}
            QListWidget::item {{
                padding: 10px;
                border-radius: 3px;
            }}
            QListWidget::item:selected {{
                background-color: {HOLO_CYAN};
                color: {HOLO_BG};
            }}
            QListWidget::item:hover {{
                background-color: {HOLO_BLUE};
            }}
            QGroupBox {{
                border: 2px solid {HOLO_PURPLE};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                color: {HOLO_TEXT};
                font-weight: bold;
            }}
            QGroupBox::title {{
                color: {HOLO_CYAN};
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            QLabel {{
                color: {HOLO_TEXT};
                font-size: 14px;
            }}
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
                background-color: {HOLO_PANEL};
                color: {HOLO_TEXT};
                border: 1px solid {HOLO_CYAN};
                border-radius: 3px;
                padding: 5px;
                min-width: 150px;
                font-size: 14px;
            }}
            QCheckBox {{
                color: {HOLO_TEXT};
                spacing: 5px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {HOLO_CYAN};
                border-radius: 3px;
                background-color: {HOLO_PANEL};
            }}
            QCheckBox::indicator:checked {{
                background-color: {HOLO_CYAN};
            }}
            QPushButton {{
                background-color: {HOLO_PANEL};
                color: {HOLO_TEXT};
                border: 2px solid {HOLO_CYAN};
                border-radius: 5px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {HOLO_CYAN};
                color: {HOLO_BG};
            }}
            QPushButton:pressed {{
                background-color: {HOLO_BLUE};
            }}
            QSlider::groove:horizontal {{
                border: 1px solid {HOLO_CYAN};
                height: 8px;
                background: {HOLO_PANEL};
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: {HOLO_CYAN};
                border: 1px solid {HOLO_CYAN};
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }}
        """)

        # Set font
        font = QFont("Courier New", 12)
        self.setFont(font)

    def get_config(self) -> SystemConfig:
        """Get updated configuration from UI."""
        # Update system settings
        self.config.system_name = self.system_name_edit.text()
        self.config.location = self.location_edit.text()

        # Update motors
        for i, widgets in enumerate(self.motor_widgets):
            motor = self.config.motors[i]
            motor.enabled = widgets['enabled'].isChecked()
            motor.name = widgets['name'].text()
            motor.steps_per_revolution = widgets['steps_per_revolution'].value()
            motor.microsteps = int(widgets['microsteps'].currentText())
            motor.max_speed_rpm = widgets['max_speed_rpm'].value()
            motor.acceleration = widgets['acceleration'].value()
            motor.current_ma = widgets['current_ma'].value()
            motor.inverted = widgets['inverted'].isChecked()

        # Update sensors
        for i, widgets in enumerate(self.sensor_widgets):
            sensor = self.config.sensors[i]
            sensor.enabled = widgets['enabled'].isChecked()
            sensor.name = widgets['name'].text()
            sensor.sensitivity = widgets['sensitivity'].value()
            sensor.update_frequency_hz = widgets['update_frequency_hz'].value()
            sensor.show_visual = widgets['show_visual'].isChecked()
            sensor.show_numeric = widgets['show_numeric'].isChecked()

        # Update power
        self.config.power.monitor_voltage = self.monitor_voltage_cb.isChecked()
        self.config.power.voltage_warning_v = self.voltage_warning_spin.value()
        self.config.power.monitor_current = self.monitor_current_cb.isChecked()
        self.config.power.current_warning_a = self.current_warning_spin.value()

        # Update UI settings
        self.config.window_title = self.window_title_edit.text()
        self.config.ui_theme = self.theme_combo.currentText()
        self.config.show_advanced_controls = self.show_advanced_cb.isChecked()

        # Update communication
        self.config.serial_timeout_s = self.serial_timeout_spin.value()
        self.config.reconnect_attempts = self.reconnect_spin.value()

        return self.config

    def accept(self):
        """Handle accept (Save button)."""
        config = self.get_config()
        self.config_changed.emit(config)
        super().accept()
