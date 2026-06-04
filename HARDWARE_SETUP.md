# Hardware Setup Guide

This guide explains how to connect and program the MKS Gen 1.4 Arduino boards with the Raspberry Pi 5.

## Overview

The raspiarduninoAI system supports two modes:
1. **Mock Hardware Mode** (default) - For testing and development without physical hardware
2. **Real Hardware Mode** - For production use with actual MKS Gen 1.4 boards

## Hardware Requirements

- Raspberry Pi 5 (or any Pi with USB ports)
- 2x MKS Gen 1.4 boards (Arduino Mega 2560 compatible)
  - Gate Board: Controls hopper gate valve and sensors
  - Telescope Board (optional): Controls telescope mount
- USB cables (USB-A to USB-B for Arduino)
- Sensors (HC-SR04 ultrasonic, dust sensor, PIR motion)

## Installation Steps

### 1. Install System Dependencies

On the Raspberry Pi, install avrdude for Arduino programming:

```bash
sudo apt-get update
sudo apt-get install avrdude
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `pyserial` - For serial communication
- `PyQt5` - For the GUI
- `pyqtgraph` - For real-time gauges

### 3. Prepare Arduino Firmware

Before connecting to the Pi, you need firmware for your boards. You have two options:

#### Option A: Pre-program on a Computer

1. Connect each MKS Gen 1.4 to your computer via USB
2. Use Arduino IDE or PlatformIO to compile and upload firmware
3. Test each board individually to verify functionality
4. Disconnect and connect to Raspberry Pi

#### Option B: Program from Raspberry Pi

The system includes Arduino programming capability via avrdude:

```python
from hardware import ArduinoProgrammer

programmer = ArduinoProgrammer()

# Program gate board
programmer.program_board(
    port="/dev/ttyUSB0",
    hex_file="/path/to/gate_firmware.hex"
)

# Program telescope board
programmer.program_board(
    port="/dev/ttyUSB1",
    hex_file="/path/to/tele_firmware.hex"
)
```

Or use command line:
```bash
avrdude -v -patmega2560 -cwiring -P/dev/ttyUSB0 -b115200 -D -Uflash:w:gate_firmware.hex:i
```

## Connecting Hardware

### Physical Connection

1. Power on Raspberry Pi
2. Connect Gate Board MKS Gen 1.4 to Pi USB port
3. (Optional) Connect Telescope Board to another USB port
4. Wait a few seconds for USB enumeration

### Verify Connections

List available serial ports:

```bash
python gui.py --list-ports
```

Expected output:
```
Available serial ports:
  /dev/ttyUSB0
  /dev/ttyUSB1

Likely Arduino boards:
  /dev/ttyUSB0
  /dev/ttyUSB1
```

### Set Permissions (if needed)

Add your user to the dialout group:

```bash
sudo usermod -a -G dialout $USER
# Log out and back in for changes to take effect
```

Or set permissions directly:
```bash
sudo chmod 666 /dev/ttyUSB0
sudo chmod 666 /dev/ttyUSB1
```

## Running the GUI

### Mock Hardware Mode (Default)

For testing without physical hardware:

```bash
python gui.py
```

### Real Hardware Mode

#### Using Command-Line Arguments:

```bash
# With one board (gate only)
python gui.py --real-hardware --gate-port /dev/ttyUSB0

# With both boards
python gui.py --real-hardware --gate-port /dev/ttyUSB0 --tele-port /dev/ttyUSB1
```

#### Using Environment Variable:

```bash
export RASPI_USE_REAL_HARDWARE=true
python gui.py
```

#### Auto-Detection:

If you don't specify ports, the system will auto-detect Arduino boards:

```bash
python gui.py --real-hardware
```

## Communication Protocol

### Arduino → Pi (Sensor Data)

The Arduino boards should send JSON-formatted sensor data over serial at 115200 baud:

```json
{
  "board_id": "GATE_001",
  "timestamp": 12345678,
  "sensors": {
    "ultrasonic_mm": 450,
    "dust": false,
    "pir_motion": false,
    "gate_open": true
  }
}
```

### Pi → Arduino (Commands)

The Pi sends text commands:

```
OPEN
CLOSE
STATUS
GET_PRESETS
```

Or G-code commands for motor control:
```
G0 X100 Y100  ; Move motors
M106 S255     ; PWM control
```

## Programming the Boards

### Method 1: Using the Hardware Module

```python
from hardware import SerialHardware

# Create hardware interface
hw = SerialHardware(
    gate_port="/dev/ttyUSB0",
    tele_port="/dev/ttyUSB1"
)

# Program gate board
if hw.program_gate_board("/path/to/firmware.hex"):
    print("Gate board programmed successfully")

# Program telescope board
if hw.program_tele_board("/path/to/firmware.hex"):
    print("Telescope board programmed successfully")
```

### Method 2: Direct avrdude

```bash
# Find your hex file
ls *.hex

# Program the board
avrdude -v -patmega2560 -cwiring -P/dev/ttyUSB0 -b115200 -D -Uflash:w:firmware.hex:i
```

### Method 3: Arduino IDE on Pi

Install Arduino IDE on Raspberry Pi:
```bash
sudo apt-get install arduino
```

Then use the IDE to program boards normally.

## Troubleshooting

### "Permission denied" on /dev/ttyUSB0

```bash
sudo chmod 666 /dev/ttyUSB0
# Or add user to dialout group (preferred)
sudo usermod -a -G dialout $USER
```

### Board not detected

1. Check USB cable (must be data cable, not charge-only)
2. Verify board has power LED on
3. Try different USB port
4. Check dmesg: `dmesg | tail -20`

### Cannot program board

1. Verify avrdude is installed: `avrdude -?`
2. Check board has bootloader
3. Try slower baud rate: `-b57600` instead of `-b115200`
4. Ensure no other program is using the serial port

### No sensor data received

1. Verify Arduino firmware is running (check Serial Monitor)
2. Check baud rate matches (115200)
3. Verify JSON format is correct
4. Check serial cable connection

### GUI shows "Failed to connect"

1. Verify pyserial is installed: `pip show pyserial`
2. Check port names: `python gui.py --list-ports`
3. Try manual port specification
4. Check system logs: `dmesg | tail`

## Python API Example

```python
from hardware import SerialHardware
from core import HopperCore

# Create hardware interface
hardware = SerialHardware(
    gate_port="/dev/ttyUSB0",
    logger=print
)

# Connect to boards
if hardware.connect(start_reading=True):
    print("Connected successfully")

    # Send commands
    hardware.send_gate("OPEN")
    hardware.send_gate("CLOSE")

    # Sensor data arrives via callback
    # See hardware.py for callback setup

# Disconnect when done
hardware.disconnect()
```

## Best Practices

1. **Always test firmware** on a computer before deploying to Pi
2. **Use proper power supplies** - MKS Gen 1.4 needs 12-24V
3. **Ground everything** - Connect all grounds together
4. **Label your cables** - Mark which USB is gate vs telescope
5. **Keep firmware updated** - Version control your Arduino code
6. **Monitor serial logs** - Watch for error messages
7. **Test incrementally** - Verify each sensor individually

## Connection Workflow

```
┌─────────────────────────────────────────┐
│  Recommended Setup Procedure             │
├─────────────────────────────────────────┤
│ 1. Compile Arduino firmware             │
│ 2. Test firmware on computer            │
│ 3. Program both boards                   │
│ 4. Verify each board individually       │
│ 5. Connect to Raspberry Pi USB          │
│ 6. Check with --list-ports              │
│ 7. Run GUI with --real-hardware         │
│ 8. Monitor logs for sensor data         │
│ 9. Test manual controls                 │
│10. Deploy for production                │
└─────────────────────────────────────────┘
```

## System Architecture

```
┌────────────────────────────────────────────┐
│         Raspberry Pi 5                     │
│  ┌──────────────────────────────────────┐  │
│  │  Python Application (gui.py)         │  │
│  │  - HolographicGUI                    │  │
│  │  - HopperCore (policy engine)        │  │
│  └────────────┬─────────────────────────┘  │
│               │                            │
│  ┌────────────▼─────────────────────────┐  │
│  │  hardware.py (SerialHardware)        │  │
│  │  - Serial communication              │  │
│  │  - Arduino programming (avrdude)     │  │
│  └──────┬──────────────────┬────────────┘  │
│         │                  │                │
│    USB  │                  │  USB           │
└─────────┼──────────────────┼────────────────┘
          │                  │
    ┌─────▼─────┐      ┌────▼──────┐
    │ MKS Gen   │      │ MKS Gen   │
    │ 1.4       │      │ 1.4       │
    │ (Gate)    │      │ (Telescope)│
    └───────────┘      └───────────┘
```

## Support

For issues:
1. Check logs in the GUI
2. Review troubleshooting section
3. Open an issue on GitHub
4. Include serial port info and error messages
