# raspiarduninoAI

Hopper gate valve + telescope control integration.

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

## Cockpit GUI

A holographic HUD-style control surface for the rig lives in
[`run_seraphina_gui.py`](run_seraphina_gui.py). It reuses the existing
`state.py` / `policies.py` / `core.py` modules to parse the gate board's JSON
sensor stream and exposes:

- Always-on cockpit gauge cluster (hopper level, valve % open, annunciator
  lamps for gate, pump, dust and flow, and the current policy decision).
- Manual controls for the gate presets (sent as `OPEN <steps>` per the
  firmware contract), the pump relay (`PUMP ON` / `PUMP OFF`), and the
  telescope.
- A **Seraphina AGI** chat panel that prefers the `seraphina` Python API and
  falls back to the installed `seraphina` CLI when no Python entry point is
  exposed.

### Run

```bash
pip install -r requirements.txt
python run_seraphina_gui.py
```

The script assumes the gate board is on `/dev/ttyACM0` and the telescope
board on `/dev/ttyACM1` at 115200 baud (the values defined at the top of the
file - adjust there if your wiring differs). Hardware and Seraphina
integrations all degrade gracefully when their backends are missing so the
HUD can be launched on a bare workstation for layout work.

## First Power-On Verification

1. Flash the gate-board firmware.
2. Open serial monitor at `115200`.
3. Confirm startup banner: `GATE_BOARD_READY`.
4. Confirm periodic JSON sensor lines are emitted.
5. Test `STATUS`, `GET_PRESETS`, `OPEN <steps>`, and `CLOSE` commands incrementally.
