#!/usr/bin/env python3
"""
Hardware interface for MKS Gen 1.4 boards via serial communication.

Supports:
- Serial communication with Arduino boards
- Sensor data reading (JSON format)
- Command sending (G-code or custom protocol)
- Arduino programming via avrdude
- Auto-detection of serial ports
"""

from __future__ import annotations

import json
import time
import subprocess
import glob
from typing import Optional, List, Callable, Dict, Any
from threading import Thread, Lock
from dataclasses import dataclass

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("Warning: pyserial not installed. Hardware communication disabled.")
    print("Install with: pip install pyserial")


@dataclass
class SerialConfig:
    """Configuration for serial communication."""
    port: str = "/dev/ttyUSB0"
    baudrate: int = 115200
    timeout: float = 1.0


@dataclass
class BoardConfig:
    """Configuration for an MKS Gen 1.4 board."""
    board_id: str
    port: str
    baudrate: int = 115200
    board_type: str = "gate"  # "gate" or "telescope"


class ArduinoProgrammer:
    """Handles programming Arduino boards via avrdude."""

    def __init__(self, logger: Optional[Callable[[str], None]] = None):
        self.logger = logger or print

    def check_avrdude_installed(self) -> bool:
        """Check if avrdude is installed."""
        try:
            result = subprocess.run(['avrdude', '-?'],
                                  capture_output=True,
                                  timeout=5)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def program_board(self, port: str, hex_file: str,
                     mcu: str = "atmega2560",
                     programmer: str = "wiring") -> bool:
        """
        Program an Arduino board using avrdude.

        Args:
            port: Serial port (e.g., /dev/ttyUSB0)
            hex_file: Path to .hex firmware file
            mcu: MCU type (default: atmega2560 for MKS Gen 1.4)
            programmer: Programmer type (default: wiring for Arduino bootloader)

        Returns:
            True if programming succeeded, False otherwise
        """
        if not self.check_avrdude_installed():
            self.logger("[ERROR] avrdude is not installed. Install with: sudo apt-get install avrdude")
            return False

        command = [
            'avrdude',
            '-v',
            f'-p{mcu}',
            f'-c{programmer}',
            f'-P{port}',
            '-b115200',
            '-D',
            f'-Uflash:w:{hex_file}:i'
        ]

        self.logger(f"[PROG] Programming {port} with {hex_file}")
        self.logger(f"[PROG] Command: {' '.join(command)}")

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                self.logger(f"[PROG] Successfully programmed {port}")
                return True
            else:
                self.logger(f"[PROG] Failed to program {port}")
                self.logger(f"[PROG] Error: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            self.logger(f"[PROG] Programming timeout for {port}")
            return False
        except Exception as e:
            self.logger(f"[PROG] Programming error: {e}")
            return False


class SerialBoard:
    """Manages serial communication with a single MKS Gen 1.4 board."""

    def __init__(self, config: BoardConfig,
                 logger: Optional[Callable[[str], None]] = None,
                 sensor_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.config = config
        self.logger = logger or print
        self.sensor_callback = sensor_callback
        self.serial = None
        self.connected = False
        self.running = False
        self.read_thread = None
        self._lock = Lock()

    def connect(self) -> bool:
        """Connect to the serial port."""
        if not SERIAL_AVAILABLE:
            self.logger(f"[{self.config.board_id}] pyserial not available")
            return False

        try:
            self.serial = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baudrate,
                timeout=1.0
            )
            time.sleep(2)  # Wait for Arduino reset
            self.connected = True
            self.logger(f"[{self.config.board_id}] Connected to {self.config.port}")
            return True
        except serial.SerialException as e:
            self.logger(f"[{self.config.board_id}] Connection failed: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from the serial port."""
        self.stop_reading()
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.connected = False
        self.logger(f"[{self.config.board_id}] Disconnected")

    def send_command(self, command: str) -> bool:
        """Send a command to the board."""
        if not self.connected or not self.serial:
            self.logger(f"[{self.config.board_id}] Not connected, cannot send: {command}")
            return False

        try:
            with self._lock:
                # Add newline if not present
                if not command.endswith('\n'):
                    command += '\n'
                self.serial.write(command.encode('utf-8'))
                self.serial.flush()
            self.logger(f"[{self.config.board_id}] Sent: {command.strip()}")
            return True
        except Exception as e:
            self.logger(f"[{self.config.board_id}] Send error: {e}")
            return False

    def read_line(self, timeout: float = 1.0) -> Optional[str]:
        """Read a single line from the serial port."""
        if not self.connected or not self.serial:
            return None

        try:
            self.serial.timeout = timeout
            line = self.serial.readline().decode('utf-8', errors='ignore').strip()
            return line if line else None
        except Exception as e:
            self.logger(f"[{self.config.board_id}] Read error: {e}")
            return None

    def _read_loop(self):
        """Background thread that continuously reads sensor data."""
        self.logger(f"[{self.config.board_id}] Read loop started")

        while self.running:
            try:
                line = self.read_line(timeout=0.5)
                if line:
                    # Try to parse as JSON sensor data
                    if line.startswith('{'):
                        try:
                            data = json.loads(line)
                            if self.sensor_callback:
                                self.sensor_callback(data)
                        except json.JSONDecodeError:
                            # Not JSON, just log it
                            self.logger(f"[{self.config.board_id}] Received: {line}")
                    else:
                        # Regular log message from Arduino
                        self.logger(f"[{self.config.board_id}] {line}")
            except Exception as e:
                if self.running:  # Only log if we're still supposed to be running
                    self.logger(f"[{self.config.board_id}] Read loop error: {e}")
                time.sleep(0.1)

        self.logger(f"[{self.config.board_id}] Read loop stopped")

    def start_reading(self):
        """Start the background reading thread."""
        if not self.connected:
            self.logger(f"[{self.config.board_id}] Cannot start reading, not connected")
            return

        if self.running:
            return

        self.running = True
        self.read_thread = Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()

    def stop_reading(self):
        """Stop the background reading thread."""
        self.running = False
        if self.read_thread:
            self.read_thread.join(timeout=2.0)


class SerialHardware:
    """
    Hardware interface for dual MKS Gen 1.4 boards (gate + telescope).

    This class provides:
    - Serial communication with both boards
    - Automatic sensor data handling
    - Command routing to appropriate board
    - Arduino programming capability
    """

    def __init__(self,
                 gate_port: str = "/dev/ttyUSB0",
                 tele_port: Optional[str] = None,
                 logger: Optional[Callable[[str], None]] = None,
                 sensor_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.logger = logger or print
        self.sensor_callback = sensor_callback

        # Initialize boards
        self.gate_board = SerialBoard(
            BoardConfig(board_id="GATE", port=gate_port, board_type="gate"),
            logger=self.logger,
            sensor_callback=self._handle_sensor_data
        )

        self.tele_board = None
        if tele_port:
            self.tele_board = SerialBoard(
                BoardConfig(board_id="TELE", port=tele_port, board_type="telescope"),
                logger=self.logger,
                sensor_callback=self._handle_sensor_data
            )

        self.programmer = ArduinoProgrammer(logger=self.logger)
        self.connected_boards: List[SerialBoard] = []

    def _handle_sensor_data(self, data: Dict[str, Any]):
        """Handle sensor data from any board."""
        if self.sensor_callback:
            self.sensor_callback(data)

    @staticmethod
    def list_serial_ports() -> List[str]:
        """List all available serial ports."""
        if not SERIAL_AVAILABLE:
            return []

        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    @staticmethod
    def auto_detect_boards() -> List[str]:
        """
        Auto-detect likely Arduino boards.

        Returns list of port names that might be Arduino boards.
        """
        if not SERIAL_AVAILABLE:
            return []

        arduino_ports = []
        ports = serial.tools.list_ports.comports()

        for port in ports:
            # Common Arduino/FTDI chips
            if any(vid in str(port) for vid in ['2341', '1A86', '0403', 'USB']):
                arduino_ports.append(port.device)

        return arduino_ports

    def connect(self, start_reading: bool = True) -> bool:
        """
        Connect to all configured boards.

        Args:
            start_reading: If True, start background reading threads

        Returns:
            True if at least one board connected successfully
        """
        success = False

        # Connect gate board
        if self.gate_board.connect():
            self.connected_boards.append(self.gate_board)
            if start_reading:
                self.gate_board.start_reading()
            success = True

        # Connect telescope board if configured
        if self.tele_board:
            if self.tele_board.connect():
                self.connected_boards.append(self.tele_board)
                if start_reading:
                    self.tele_board.start_reading()
                success = True

        return success

    def disconnect(self):
        """Disconnect from all boards."""
        for board in self.connected_boards:
            board.disconnect()
        self.connected_boards.clear()

    def is_connected(self) -> bool:
        """Check if any boards are connected."""
        return len(self.connected_boards) > 0

    def send_gate(self, command: str) -> None:
        """Send command to gate controller (HardwareProtocol interface)."""
        self.gate_board.send_command(command)

    def send_tele(self, command: str) -> None:
        """Send command to telescope controller (HardwareProtocol interface)."""
        if self.tele_board:
            self.tele_board.send_command(command)
        else:
            self.logger("[TELE] No telescope board configured")

    def program_gate_board(self, hex_file: str) -> bool:
        """Program the gate board with firmware."""
        return self.programmer.program_board(self.gate_board.config.port, hex_file)

    def program_tele_board(self, hex_file: str) -> bool:
        """Program the telescope board with firmware."""
        if not self.tele_board:
            self.logger("[TELE] No telescope board configured")
            return False
        return self.programmer.program_board(self.tele_board.config.port, hex_file)


def create_hardware_from_config(config_file: Optional[str] = None,
                                logger: Optional[Callable[[str], None]] = None,
                                sensor_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> SerialHardware:
    """
    Create hardware interface from configuration file.

    If no config file is provided, attempts auto-detection.
    """
    # Try auto-detection if no config
    ports = SerialHardware.auto_detect_boards()

    gate_port = ports[0] if len(ports) > 0 else "/dev/ttyUSB0"
    tele_port = ports[1] if len(ports) > 1 else None

    if logger:
        logger(f"[HARDWARE] Detected ports: {ports}")
        logger(f"[HARDWARE] Using gate port: {gate_port}")
        if tele_port:
            logger(f"[HARDWARE] Using tele port: {tele_port}")

    return SerialHardware(
        gate_port=gate_port,
        tele_port=tele_port,
        logger=logger,
        sensor_callback=sensor_callback
    )
