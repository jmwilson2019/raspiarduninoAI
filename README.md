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

## First Power-On Verification

1. Flash the gate-board firmware.
2. Open serial monitor at `115200`.
3. Confirm startup banner: `GATE_BOARD_READY`.
4. Confirm periodic JSON sensor lines are emitted.
5. Test `STATUS`, `GET_PRESETS`, `OPEN <steps>`, and `CLOSE` commands incrementally.
