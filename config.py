#!/usr/bin/env python3
"""
Configuration management for raspiarduninoAI.

Handles:
- Motor configuration (NEMA 17 steppers)
- Sensor settings with sensitivity
- System preferences
- Password-protected advanced settings
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from pathlib import Path


@dataclass
class MotorConfig:
    """Configuration for a single stepper motor."""
    name: str = "Motor"
    enabled: bool = True
    steps_per_revolution: int = 200  # NEMA 17 standard
    microsteps: int = 16
    max_speed_rpm: int = 60
    acceleration: int = 500
    current_ma: int = 1000
    inverted: bool = False

    @property
    def steps_per_minute(self) -> int:
        """Calculate steps per minute."""
        return self.steps_per_revolution * self.microsteps * self.max_speed_rpm


@dataclass
class SensorConfig:
    """Configuration for a sensor."""
    name: str = "Sensor"
    enabled: bool = True
    sensor_type: str = "ultrasonic"  # ultrasonic, dust, pir, etc.
    pin: int = 0

    # Sensitivity settings
    sensitivity: int = 50  # 0-100 scale
    update_frequency_hz: int = 10

    # Thresholds
    threshold_low: Optional[float] = None
    threshold_high: Optional[float] = None

    # Display settings
    show_visual: bool = True
    show_numeric: bool = True
    color: str = "#00FFFF"


@dataclass
class UltrasonicSensorConfig(SensorConfig):
    """Ultrasonic-specific configuration."""
    sensor_type: str = "ultrasonic"
    min_distance_mm: int = 20
    max_distance_mm: int = 4000
    trigger_distance_mm: int = 600
    show_beam_visualization: bool = True


@dataclass
class PowerConfig:
    """Power monitoring configuration."""
    monitor_voltage: bool = False
    monitor_current: bool = False
    voltage_warning_v: float = 11.0
    current_warning_a: float = 5.0


@dataclass
class SystemConfig:
    """Main system configuration."""
    # System identification
    system_name: str = "raspiarduninoAI"
    location: str = "Lab"

    # Motors
    motors: List[MotorConfig] = field(default_factory=lambda: [
        MotorConfig(name="Gate Motor 1"),
        MotorConfig(name="Gate Motor 2"),
        MotorConfig(name="Telescope X", enabled=False),
        MotorConfig(name="Telescope Y", enabled=False),
    ])

    # Sensors
    sensors: List[SensorConfig] = field(default_factory=lambda: [
        UltrasonicSensorConfig(name="Material Level", threshold_high=600.0),
        SensorConfig(name="Dust Sensor", sensor_type="dust"),
        SensorConfig(name="PIR Motion", sensor_type="pir"),
        SensorConfig(name="Gate Position", sensor_type="limit_switch"),
    ])

    # Power monitoring
    power: PowerConfig = field(default_factory=PowerConfig)

    # UI Settings
    ui_theme: str = "holographic"
    show_advanced_controls: bool = False
    window_title: str = "raspiarduninoAI - Holographic Control"

    # Communication
    serial_timeout_s: float = 1.0
    reconnect_attempts: int = 3

    # Security
    password_hash: Optional[str] = None
    require_password_for_advanced: bool = True

    def set_password(self, password: str):
        """Set the master password."""
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()

    def check_password(self, password: str) -> bool:
        """Check if password is correct."""
        if self.password_hash is None:
            return True  # No password set
        return hashlib.sha256(password.encode()).hexdigest() == self.password_hash


class ConfigManager:
    """Manages configuration loading, saving, and validation."""

    DEFAULT_CONFIG_PATH = Path.home() / ".raspiarduninoai" / "config.json"

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = SystemConfig()

    def load(self) -> SystemConfig:
        """Load configuration from file."""
        if not self.config_path.exists():
            return self.config

        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)

            # Reconstruct motor configs
            motors = []
            for motor_data in data.get('motors', []):
                motors.append(MotorConfig(**motor_data))

            # Reconstruct sensor configs
            sensors = []
            for sensor_data in data.get('sensors', []):
                sensor_type = sensor_data.get('sensor_type', 'generic')
                if sensor_type == 'ultrasonic':
                    sensors.append(UltrasonicSensorConfig(**sensor_data))
                else:
                    sensors.append(SensorConfig(**sensor_data))

            # Reconstruct power config
            power = PowerConfig(**data.get('power', {}))

            # Create system config
            self.config = SystemConfig(
                system_name=data.get('system_name', 'raspiarduninoAI'),
                location=data.get('location', 'Lab'),
                motors=motors,
                sensors=sensors,
                power=power,
                ui_theme=data.get('ui_theme', 'holographic'),
                show_advanced_controls=data.get('show_advanced_controls', False),
                window_title=data.get('window_title', 'raspiarduninoAI - Holographic Control'),
                serial_timeout_s=data.get('serial_timeout_s', 1.0),
                reconnect_attempts=data.get('reconnect_attempts', 3),
                password_hash=data.get('password_hash'),
                require_password_for_advanced=data.get('require_password_for_advanced', True),
            )

            return self.config

        except Exception as e:
            print(f"Error loading config: {e}")
            return self.config

    def save(self, config: Optional[SystemConfig] = None):
        """Save configuration to file."""
        if config:
            self.config = config

        # Ensure directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict
        data = {
            'system_name': self.config.system_name,
            'location': self.config.location,
            'motors': [asdict(m) for m in self.config.motors],
            'sensors': [asdict(s) for s in self.config.sensors],
            'power': asdict(self.config.power),
            'ui_theme': self.config.ui_theme,
            'show_advanced_controls': self.config.show_advanced_controls,
            'window_title': self.config.window_title,
            'serial_timeout_s': self.config.serial_timeout_s,
            'reconnect_attempts': self.config.reconnect_attempts,
            'password_hash': self.config.password_hash,
            'require_password_for_advanced': self.config.require_password_for_advanced,
        }

        try:
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def reset_to_defaults(self):
        """Reset configuration to defaults."""
        self.config = SystemConfig()
        return self.config

    def export_config(self, path: Path) -> bool:
        """Export configuration to a specific file."""
        original_path = self.config_path
        self.config_path = path
        result = self.save()
        self.config_path = original_path
        return result

    def import_config(self, path: Path) -> Optional[SystemConfig]:
        """Import configuration from a specific file."""
        original_path = self.config_path
        self.config_path = path
        config = self.load()
        self.config_path = original_path
        return config
