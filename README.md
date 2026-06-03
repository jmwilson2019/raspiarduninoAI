# raspiarduninoAI

Hopper gate valve + telescope control integration with holographic GUI.

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

### Mock Hardware Mode (Testing)

```bash
python gui.py
```

### Real Hardware Mode (Production)

```bash
# Auto-detect Arduino boards
python gui.py --real-hardware

# Specify ports manually
python gui.py --real-hardware --gate-port /dev/ttyUSB0 --tele-port /dev/ttyUSB1

# List available ports
python gui.py --list-ports
```

**For detailed hardware setup instructions, see [HARDWARE_SETUP.md](HARDWARE_SETUP.md)**

## Usage

This library provides a policy-based control system for managing a hopper gate valve based on sensor inputs (ultrasonic distance, dust detection, PIR motion).

### Holographic GUI

Launch the holographic GUI interface for real-time monitoring and control:

```bash
python gui.py
```

**Features:**
- 🌟 Futuristic holographic design with neon cyan/purple theme
- 📊 Real-time sensor monitoring with animated circular gauges
- 🎮 Manual control interface for gate operations
- 🚨 Live alert notifications and system status
- 📝 Real-time system log with color-coded messages
- ⚡ Smooth animations and visual effects

The GUI provides:
- **Sensor Telemetry Panel**: Live gauges showing material level and gate status
- **System Status Panel**: Detailed sensor readings and active alerts
- **Manual Controls Panel**: Buttons to open/close gate and simulate sensor events
- **System Log**: Real-time logging of all system events

### Basic Example

```python
from core import build_default_core
from policies import PolicyConfig, PolicyEngine

# Implement the hardware interface
class MyHardware:
    def send_gate(self, command: str) -> None:
        # Send command to gate controller
        print(f"Gate: {command}")

    def send_tele(self, command: str) -> None:
        # Send command to telescope controller
        print(f"Telescope: {command}")

# Create the control system
hardware = MyHardware()
core = build_default_core(hardware=hardware, logger=print)

# Process sensor data
sensor_payload = {
    "board_id": "GATE_001",
    "timestamp": 12345,
    "sensors": {
        "ultrasonic_mm": 450,  # Material level
        "dust": False,
        "pir_motion": False,
        "gate_open": True
    }
}

decision = core.on_sensor_payload(sensor_payload)
```

### Custom Policy Configuration

```python
from policies import PolicyConfig

# Configure custom thresholds and behaviors
config = PolicyConfig(
    stale_after_s=5.0,              # Consider data stale after 5 seconds
    low_material_distance_mm=500,   # Close gate when material < 500mm
    close_on_dust=True,             # Close gate on dust detection
    close_on_motion=True            # Close gate on PIR motion
)

policy_engine = PolicyEngine(config)
core = HopperCore(hardware=hardware, policy_engine=policy_engine)
```

For more examples, see `example.py`.

## Running Tests

```bash
# Run all tests
pytest test_state.py test_policies.py test_core.py test_gui.py -v

# Run tests without GUI tests (if display not available)
pytest test_state.py test_policies.py test_core.py -v

# Run with coverage
pytest -v --cov=. --cov-report=term-missing
```

## Architecture

- **`state.py`**: Manages sensor state and data validation
- **`policies.py`**: Policy engine that evaluates sensor state and makes decisions
- **`core.py`**: Core controller that coordinates state, policy, and hardware interfaces
- **`gui.py`**: Holographic GUI for real-time monitoring and control

## Wiring

### Gate Board (MKS Gen V1.4) Final Pin Assignments

| Component | Pin / Header | Notes |
|---|---|---|
| Gate Motor 1 | X (54 STEP, 55 DIR) | Standard |
| Gate Motor 2 | Y (60 STEP, 61 DIR) | Firmware-commanded to same target as motor 1 |
| Enable (both) | 38 | Active LOW |
| Pump Relay | Heatbed (8) | High-current relay output |
| Valve (PWM) | Hotend (9) | PWM range 0-255 (`0` closed, `255` full-open, intermediate = partial) |
| HC-SR04 Trig | 17 | Digital output |
| HC-SR04 Echo | 16 | Digital input |
| Dust Sensor OUT | 18 | Digital input |
| PIR (HC-SR501) OUT | 19 | Digital input |
| Sensor Power | 5V / GND headers | Shared 5V/GND rail |

### Telescope Board

Telescope board wiring is unchanged from the existing 4-motor telescope setup.

## Wiring Notes

- Tie all sensor grounds to the same board ground reference.
- Confirm the gate enable logic is active LOW before first motion test (`LOW` = drivers enabled, `HIGH` = disabled) to avoid unexpected movement.
- Keep high-current pump relay wiring isolated from low-voltage sensor leads.
- Verify HC-SR04 orientation and stable 5V supply before trusting distance data.

## First Power-On Verification

1. Flash the gate-board firmware.
2. Open serial monitor at `115200`.
3. Confirm startup banner: `GATE_BOARD_READY`.
4. Confirm periodic JSON sensor lines are emitted.
5. Test `STATUS`, `GET_PRESETS`, `OPEN <steps>`, and `CLOSE` commands incrementally.
