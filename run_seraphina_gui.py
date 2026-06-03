"""Cockpit-style control GUI for the Seraphina hopper + telescope rig.

This script wires together:

* The existing :mod:`state` / :mod:`policies` / :mod:`core` modules (left
  untouched - they already parse the gate board's JSON sensor payloads and
  derive safety actions such as auto-closing the valve on dust or low
  material).
* The Arduino-side firmware that lives on the MKS Gen V1.4 gate board and a
  second MKS board driving the telescope.  Firmware is not modified by this
  GUI; the wiring documented in ``README.md`` is assumed:

    - Hotend (pin 9, PWM) drives the gate valve (``OPEN <steps>`` / ``CLOSE``).
    - Heatbed (pin 8, relay) switches the pump (``PUMP ON`` / ``PUMP OFF``).
    - HC-SR04, dust sensor and PIR live on digital pins and are reported back
      in the periodic JSON line emitted by the gate board.

* The Seraphina AGI runtime (``seraphina-agi`` on PyPI - same author as this
  repository).  If the Python API is importable it is preferred; otherwise the
  ``seraphina`` CLI is invoked via :mod:`subprocess` as a fallback.

The UI is laid out like a small cockpit: a permanent gauge cluster sits above
the controls so the operator can always see hopper level, valve opening, pump
state, dust and flow indicators at a glance.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import threading
import time
import tkinter as tk
from datetime import datetime
from typing import Any, Dict, Optional

import customtkinter as ctk

try:  # pragma: no cover - optional dependency at runtime
    import serial  # type: ignore
except ImportError:  # pragma: no cover - allows GUI to start without pyserial
    serial = None  # type: ignore[assignment]

from core import HopperCore
from policies import PolicyDecision, PolicyEngine
from state import StateStore

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GATE_PORT = "/dev/ttyACM0"
TELE_PORT = "/dev/ttyACM1"
SERIAL_BAUD = 115200

# Gate firmware expects ``OPEN <steps>`` per README; map cockpit presets to the
# step counts the firmware understands.  Adjust here without touching firmware.
GATE_PRESETS: Dict[str, int] = {
    '1/4"': 400,
    '1/2"': 800,
    '3/4"': 1200,
    '1"': 1600,
    "Full": 2400,
}

# Hopper level scale used by the level gauge (mm reported by HC-SR04).
LEVEL_GAUGE_MAX_MM = 800
LEVEL_LOW_WARN_MM = 600  # matches PolicyConfig.low_material_distance_mm

SENSOR_POLL_INTERVAL_S = 0.15
UI_REFRESH_INTERVAL_MS = 150

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ---------------------------------------------------------------------------
# Holographic HUD palette
# ---------------------------------------------------------------------------
#
# The rig drives a plain HDMI panel; "holographic" here means we lean into a
# sci-fi heads-up display look - very dark backdrop, glowing cyan/teal accents,
# thin neon frames and monospace type.  All cosmetic, no extra dependencies.

HOLO_BG = "#04101a"
HOLO_BG_PANEL = "#071a26"
HOLO_GRID = "#0a2c3a"
HOLO_ACCENT = "#00e5ff"
HOLO_ACCENT_DIM = "#0c5566"
HOLO_ACCENT_GLOW = "#33f0ff"
HOLO_OK = "#00ffae"
HOLO_WARN = "#ffcc33"
HOLO_ALARM = "#ff4b6b"
HOLO_MUTED = "#1d3340"
HOLO_TEXT = "#bfeefa"

HUD_FONT_FAMILY = "Consolas"  # falls back to system monospace if unavailable

# ---------------------------------------------------------------------------
# Seraphina AGI bridge
# ---------------------------------------------------------------------------


class SeraphinaBridge:
    """Best-effort adapter for talking to the Seraphina AGI runtime.

    The package exposes a few different surfaces depending on version; we try
    the most likely Python entry points first and fall back to the installed
    ``seraphina`` CLI.  Every public method is safe to call even when nothing
    is installed - it simply returns an explanatory string.
    """

    def __init__(self) -> None:
        self._py_callable = self._discover_python_api()
        self._cli_path = shutil.which("seraphina")

    @staticmethod
    def _discover_python_api():
        candidates = (
            ("seraphina", "chat"),
            ("seraphina", "ask"),
            ("seraphina", "run"),
            ("seraphina.agi", "chat"),
            ("seraphina.agi", "ask"),
        )
        for module_name, attr in candidates:
            try:
                module = __import__(module_name, fromlist=[attr])
            except Exception:
                continue
            func = getattr(module, attr, None)
            if callable(func):
                return func
        return None

    @property
    def available(self) -> bool:
        return self._py_callable is not None or self._cli_path is not None

    @property
    def backend(self) -> str:
        if self._py_callable is not None:
            return "python-api"
        if self._cli_path is not None:
            return "cli"
        return "unavailable"

    def ask(self, prompt: str, timeout_s: float = 15.0) -> str:
        prompt = prompt.strip()
        if not prompt:
            return ""

        if self._py_callable is not None:
            try:
                result = self._py_callable(prompt)
                if result is None:
                    return ""
                return str(result).strip()
            except Exception as exc:  # pragma: no cover - depends on runtime
                return f"Seraphina Python API error: {exc}"

        if self._cli_path is not None:
            try:
                completed = subprocess.run(
                    [self._cli_path, prompt],
                    capture_output=True,
                    text=True,
                    timeout=timeout_s,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return f"Seraphina CLI timed out after {timeout_s:.0f}s"
            except Exception as exc:  # pragma: no cover - depends on runtime
                return f"Seraphina CLI error: {exc}"
            output = (completed.stdout or "").strip()
            if not output:
                output = (completed.stderr or "").strip()
            return output or "(Seraphina returned no output)"

        return (
            "Seraphina runtime not detected. Install with `pip install seraphina-agi` "
            "to enable AGI assistance."
        )


# ---------------------------------------------------------------------------
# Custom cockpit widgets
# ---------------------------------------------------------------------------


class ArcGauge(ctk.CTkFrame):
    """A simple semi-circular gauge rendered on a Tk canvas.

    The gauge is intentionally lightweight (no extra dependencies) so it can
    render comfortably on a Raspberry Pi.
    """

    def __init__(
        self,
        master: Any,
        *,
        title: str,
        unit: str,
        minimum: float = 0.0,
        maximum: float = 100.0,
        size: int = 240,
    ) -> None:
        super().__init__(
            master,
            corner_radius=14,
            fg_color=HOLO_BG_PANEL,
            border_width=1,
            border_color=HOLO_ACCENT_DIM,
        )
        self._title = title
        self._unit = unit
        self._min = float(minimum)
        self._max = float(maximum)
        self._size = size
        self._value: Optional[float] = None
        self._color = HOLO_ACCENT

        ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(family=HUD_FONT_FAMILY, size=13, weight="bold"),
            text_color=HOLO_ACCENT,
        ).pack(pady=(10, 4))

        self._canvas = tk.Canvas(
            self,
            width=size,
            height=int(size * 0.68),
            bg=HOLO_BG_PANEL,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack(padx=12)

        self._value_label = ctk.CTkLabel(
            self,
            text="---",
            font=ctk.CTkFont(family=HUD_FONT_FAMILY, size=22, weight="bold"),
            text_color=HOLO_TEXT,
        )
        self._value_label.pack(pady=(2, 10))

        self._draw_background()

    @staticmethod
    def _theme_bg() -> str:
        return HOLO_BG_PANEL

    def _arc_box(self, padding: int = 16):
        size = self._size
        return padding, padding, size - padding, size - padding

    def _draw_background(self) -> None:
        self._canvas.delete("all")
        x0, y0, x1, y1 = self._arc_box()

        # Faint outer ring + inner ring for the holographic concentric feel.
        for inset, color in ((-6, HOLO_GRID), (0, HOLO_ACCENT_DIM), (10, HOLO_GRID)):
            self._canvas.create_arc(
                x0 + inset,
                y0 + inset,
                x1 - inset,
                y1 - inset,
                start=180,
                extent=-180,
                style="arc",
                width=1,
                outline=color,
            )

        # Background track for the active arc.
        self._canvas.create_arc(
            x0,
            y0,
            x1,
            y1,
            start=180,
            extent=-180,
            style="arc",
            width=12,
            outline=HOLO_MUTED,
        )

        # Tick marks every 18 degrees (= every 10% of scale) for the HUD look.
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2
        radius_outer = (x1 - x0) / 2 + 4
        radius_inner = radius_outer - 8
        for i in range(11):
            angle = math.radians(180 + (-180) * (i / 10))
            ox = cx + radius_outer * math.cos(angle)
            oy = cy - radius_outer * math.sin(angle)
            ix = cx + radius_inner * math.cos(angle)
            iy = cy - radius_inner * math.sin(angle)
            self._canvas.create_line(ix, iy, ox, oy, fill=HOLO_ACCENT_DIM, width=1)

    def set_value(self, value: Optional[float], *, color: Optional[str] = None) -> None:
        if color is not None:
            self._color = color
        self._value = value
        self._draw_background()

        if value is None:
            self._value_label.configure(text="---", text_color=HOLO_MUTED)
            return

        clamped = max(self._min, min(self._max, value))
        span = self._max - self._min or 1.0
        fraction = (clamped - self._min) / span
        extent = -180 * fraction

        x0, y0, x1, y1 = self._arc_box()
        if abs(extent) > 0.5:
            # Multi-pass glow: thick translucent halo, then the bright core arc.
            for width, outline in (
                (18, HOLO_ACCENT_DIM),
                (12, self._color),
                (4, HOLO_ACCENT_GLOW),
            ):
                self._canvas.create_arc(
                    x0,
                    y0,
                    x1,
                    y1,
                    start=180,
                    extent=extent,
                    style="arc",
                    width=width,
                    outline=outline,
                )

        # Glowing needle with hub.
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2
        radius = (x1 - x0) / 2 - 6
        angle_rad = math.radians(180 + extent)
        nx = cx + radius * math.cos(angle_rad)
        ny = cy - radius * math.sin(angle_rad)
        self._canvas.create_line(cx, cy, nx, ny, fill=HOLO_ACCENT_DIM, width=5)
        self._canvas.create_line(cx, cy, nx, ny, fill=self._color, width=2)
        self._canvas.create_oval(cx - 8, cy - 8, cx + 8, cy + 8, outline=HOLO_ACCENT, width=1)
        self._canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=self._color, outline="")

        self._value_label.configure(text=f"{value:.0f} {self._unit}", text_color=self._color)


class StatusLamp(ctk.CTkFrame):
    """Indicator lamp with a label - mirrors aircraft annunciator panels."""

    COLORS = {
        "ok": HOLO_OK,
        "warn": HOLO_WARN,
        "alarm": HOLO_ALARM,
        "info": HOLO_ACCENT,
        "off": HOLO_MUTED,
    }

    def __init__(self, master: Any, *, label: str) -> None:
        super().__init__(
            master,
            corner_radius=10,
            fg_color=HOLO_BG_PANEL,
            border_width=1,
            border_color=HOLO_ACCENT_DIM,
        )
        self._label_text = label
        self._state = "off"

        self._dot = tk.Canvas(
            self,
            width=30,
            height=30,
            bg=HOLO_BG_PANEL,
            highlightthickness=0,
            bd=0,
        )
        self._dot.pack(side="left", padx=(12, 8), pady=6)

        self._text = ctk.CTkLabel(
            self,
            text=label,
            font=ctk.CTkFont(family=HUD_FONT_FAMILY, size=12, weight="bold"),
            text_color=HOLO_TEXT,
        )
        self._text.pack(side="left", padx=(0, 12), pady=6)

        self._render_dot()

    def _render_dot(self) -> None:
        color = self.COLORS.get(self._state, self.COLORS["off"])
        self._dot.delete("all")
        # Outer halo ring for the holographic glow.
        self._dot.create_oval(2, 2, 28, 28, outline=color, width=1)
        self._dot.create_oval(6, 6, 24, 24, outline=color, width=1)
        if self._state != "off":
            self._dot.create_oval(10, 10, 20, 20, fill=color, outline="")

    def set_state(self, state: str, *, label: Optional[str] = None) -> None:
        self._state = state
        if label is not None:
            self._label_text = label
        self._text.configure(text=self._label_text)
        self._render_dot()


# ---------------------------------------------------------------------------
# Hardware adapter for HopperCore
# ---------------------------------------------------------------------------


class SerialHardware:
    """Bridges :class:`HopperCore` decisions to the gate / telescope serial ports."""

    def __init__(self, app: "SeraphinaCockpitGUI") -> None:
        self._app = app

    def send_gate(self, command: str) -> None:
        self._app.write_gate(command, origin="policy")

    def send_tele(self, command: str) -> None:
        self._app.write_tele(command, origin="policy")


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------


class SeraphinaCockpitGUI:
    def __init__(self) -> None:
        self.root = ctk.CTk()
        self.root.title("Seraphina AGI - Hopper Cockpit")
        self.root.geometry("1280x820")
        self.root.minsize(1100, 720)

        self.gate_ser: Optional[Any] = None
        self.tele_ser: Optional[Any] = None

        self.state_store = StateStore()
        self.policy_engine = PolicyEngine()
        self.hopper_core = HopperCore(
            hardware=SerialHardware(self),
            state_store=self.state_store,
            policy_engine=self.policy_engine,
            logger=self._log_threadsafe,
        )

        self.seraphina = SeraphinaBridge()

        self.current_preset = next(iter(GATE_PRESETS))
        self.valve_open_pct: float = 0.0
        self.pump_on = False
        self._stop_event = threading.Event()

        self._build_ui()
        self._connect_hardware()
        self._start_sensor_thread()

    # -- UI construction ---------------------------------------------------

    def _build_ui(self) -> None:
        self.root.configure(fg_color=HOLO_BG)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(
            self.root,
            corner_radius=0,
            fg_color=HOLO_BG_PANEL,
            border_width=0,
        )
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header,
            text="\u25c6  SERAPHINA AGI  \u00b7  HOPPER COCKPIT  \u25c6",
            font=ctk.CTkFont(family=HUD_FONT_FAMILY, size=22, weight="bold"),
            text_color=HOLO_ACCENT,
        ).grid(row=0, column=0, padx=20, pady=12, sticky="w")

        self.clock_label = ctk.CTkLabel(
            header,
            text="--:--:--",
            font=ctk.CTkFont(family=HUD_FONT_FAMILY, size=14),
            text_color=HOLO_TEXT,
        )
        self.clock_label.grid(row=0, column=1, sticky="e", padx=20)

        link_frame = ctk.CTkFrame(header, fg_color="transparent")
        link_frame.grid(row=0, column=2, padx=20, sticky="e")
        self.gate_link_lamp = StatusLamp(link_frame, label="GATE LINK")
        self.gate_link_lamp.pack(side="left", padx=6)
        self.tele_link_lamp = StatusLamp(link_frame, label="TELE LINK")
        self.tele_link_lamp.pack(side="left", padx=6)
        self.agi_lamp = StatusLamp(link_frame, label="SERAPHINA")
        self.agi_lamp.pack(side="left", padx=6)

        # ---- Cockpit gauge cluster (with holographic grid backdrop) -----
        cockpit_wrap = ctk.CTkFrame(self.root, corner_radius=0, fg_color=HOLO_BG)
        cockpit_wrap.grid(row=1, column=0, sticky="ew", padx=12, pady=(8, 4))
        cockpit_wrap.grid_columnconfigure(0, weight=1)

        self._grid_canvas = tk.Canvas(
            cockpit_wrap,
            height=320,
            bg=HOLO_BG,
            highlightthickness=0,
            bd=0,
        )
        self._grid_canvas.grid(row=0, column=0, sticky="nsew")
        self._grid_canvas.bind("<Configure>", self._draw_hud_grid)

        cockpit = ctk.CTkFrame(cockpit_wrap, corner_radius=0, fg_color="transparent")
        cockpit.place(in_=self._grid_canvas, relx=0, rely=0, relwidth=1, relheight=1)
        for col in range(4):
            cockpit.grid_columnconfigure(col, weight=1)
        cockpit.grid_rowconfigure(0, weight=1)

        self.level_gauge = ArcGauge(
            cockpit,
            title="HOPPER LEVEL",
            unit="mm",
            minimum=0,
            maximum=LEVEL_GAUGE_MAX_MM,
        )
        self.level_gauge.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self.valve_gauge = ArcGauge(
            cockpit,
            title="VALVE OPEN",
            unit="%",
            minimum=0,
            maximum=100,
        )
        self.valve_gauge.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        lamp_panel = ctk.CTkFrame(
            cockpit,
            corner_radius=12,
            fg_color=HOLO_BG_PANEL,
            border_width=1,
            border_color=HOLO_ACCENT_DIM,
        )
        lamp_panel.grid(row=0, column=2, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(
            lamp_panel,
            text="ANNUNCIATOR",
            font=ctk.CTkFont(family=HUD_FONT_FAMILY, size=13, weight="bold"),
            text_color=HOLO_ACCENT,
        ).pack(pady=(10, 6))
        self.gate_lamp = StatusLamp(lamp_panel, label="GATE CLOSED")
        self.gate_lamp.pack(fill="x", padx=12, pady=4)
        self.pump_lamp = StatusLamp(lamp_panel, label="PUMP OFF")
        self.pump_lamp.pack(fill="x", padx=12, pady=4)
        self.dust_lamp = StatusLamp(lamp_panel, label="MATERIAL OK")
        self.dust_lamp.pack(fill="x", padx=12, pady=4)
        self.flow_lamp = StatusLamp(lamp_panel, label="FLOW ---")
        self.flow_lamp.pack(fill="x", padx=12, pady=4)

        policy_panel = ctk.CTkFrame(
            cockpit,
            corner_radius=12,
            fg_color=HOLO_BG_PANEL,
            border_width=1,
            border_color=HOLO_ACCENT_DIM,
        )
        policy_panel.grid(row=0, column=3, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(
            policy_panel,
            text="POLICY",
            font=ctk.CTkFont(family=HUD_FONT_FAMILY, size=13, weight="bold"),
            text_color=HOLO_ACCENT,
        ).pack(pady=(10, 6))
        self.policy_text = ctk.CTkTextbox(
            policy_panel,
            height=160,
            width=240,
            fg_color=HOLO_BG,
            border_color=HOLO_ACCENT_DIM,
            border_width=1,
            text_color=HOLO_TEXT,
            font=ctk.CTkFont(family=HUD_FONT_FAMILY, size=12),
        )
        self.policy_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.policy_text.configure(state="disabled")

        # ---- Controls + log split --------------------------------------
        body = ctk.CTkFrame(self.root, corner_radius=0, fg_color=HOLO_BG)
        body.grid(row=2, column=0, sticky="nsew", padx=12, pady=(4, 4))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_gate_controls(body)
        self._build_right_panel(body)

        # ---- Status bar -------------------------------------------------
        self.status_bar = ctk.CTkLabel(
            self.root,
            text="Initializing...",
            anchor="w",
            font=ctk.CTkFont(family=HUD_FONT_FAMILY, size=12),
            text_color=HOLO_TEXT,
            fg_color=HOLO_BG_PANEL,
        )
        self.status_bar.grid(row=3, column=0, sticky="ew", padx=0, pady=(0, 0))

        # Initialize annunciator defaults.
        self.gate_lamp.set_state("ok", label="GATE CLOSED")
        self.pump_lamp.set_state("off", label="PUMP OFF")
        self.dust_lamp.set_state("ok", label="MATERIAL OK")
        self.flow_lamp.set_state("off", label="FLOW ---")
        self.gate_link_lamp.set_state("off")
        self.tele_link_lamp.set_state("off")

        if self.seraphina.available:
            self.agi_lamp.set_state("ok", label=f"SERAPHINA ({self.seraphina.backend})")
        else:
            self.agi_lamp.set_state("warn", label="SERAPHINA N/A")

        self._tick_clock()
        self.root.after(UI_REFRESH_INTERVAL_MS, self._refresh_ui)

    def _build_gate_controls(self, parent: Any) -> None:
        frame = ctk.CTkFrame(
            parent,
            corner_radius=12,
            fg_color=HOLO_BG_PANEL,
            border_width=1,
            border_color=HOLO_ACCENT_DIM,
        )
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        ctk.CTkLabel(
            frame,
            text="\u25b8 GATE & PUMP",
            font=ctk.CTkFont(family=HUD_FONT_FAMILY, size=15, weight="bold"),
            text_color=HOLO_ACCENT,
        ).pack(pady=(12, 8))

        preset_row = ctk.CTkFrame(frame, fg_color="transparent")
        preset_row.pack(pady=4)
        ctk.CTkLabel(
            preset_row,
            text="Preset:",
            text_color=HOLO_TEXT,
            font=ctk.CTkFont(family=HUD_FONT_FAMILY, size=12),
        ).pack(side="left", padx=(0, 8))
        self.preset_combo = ctk.CTkComboBox(
            preset_row,
            values=list(GATE_PRESETS.keys()),
            command=self._on_preset_change,
            width=140,
            fg_color=HOLO_BG,
            border_color=HOLO_ACCENT_DIM,
            button_color=HOLO_ACCENT_DIM,
            button_hover_color=HOLO_ACCENT,
            text_color=HOLO_TEXT,
            dropdown_fg_color=HOLO_BG_PANEL,
            dropdown_text_color=HOLO_TEXT,
        )
        self.preset_combo.set(self.current_preset)
        self.preset_combo.pack(side="left")

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(pady=14)
        self._holo_button(
            btn_row, text="OPEN GATE", command=self.open_gate, accent=HOLO_OK
        ).grid(row=0, column=0, padx=10)
        self._holo_button(
            btn_row, text="CLOSE GATE", command=self.close_gate, accent=HOLO_ALARM
        ).grid(row=0, column=1, padx=10)

        pump_row = ctk.CTkFrame(frame, fg_color="transparent")
        pump_row.pack(pady=10)
        self._holo_button(
            pump_row,
            text="PUMP ON",
            command=lambda: self.set_pump(True),
            accent=HOLO_ACCENT,
            height=46,
        ).grid(row=0, column=0, padx=10)
        self._holo_button(
            pump_row,
            text="PUMP OFF",
            command=lambda: self.set_pump(False),
            accent=HOLO_MUTED,
            height=46,
        ).grid(row=0, column=1, padx=10)

        # Telescope controls live in this same column under a separator.
        ctk.CTkFrame(frame, height=1, fg_color=HOLO_ACCENT_DIM).pack(fill="x", padx=20, pady=(16, 8))
        ctk.CTkLabel(
            frame,
            text="\u25b8 TELESCOPE",
            font=ctk.CTkFont(family=HUD_FONT_FAMILY, size=15, weight="bold"),
            text_color=HOLO_ACCENT,
        ).pack(pady=(4, 8))
        tele_row = ctk.CTkFrame(frame, fg_color="transparent")
        tele_row.pack(pady=4)
        self._holo_button(
            tele_row,
            text="\u25b2  TELESCOPE UP",
            command=lambda: self.write_tele("TELE_UP", origin="manual"),
            accent=HOLO_ACCENT,
            height=50,
            width=200,
        ).grid(row=0, column=0, padx=10, pady=4)
        self._holo_button(
            tele_row,
            text="\u25bc  TELESCOPE DOWN",
            command=lambda: self.write_tele("TELE_DOWN", origin="manual"),
            accent=HOLO_ACCENT,
            height=50,
            width=200,
        ).grid(row=0, column=1, padx=10, pady=4)

    def _holo_button(
        self,
        parent: Any,
        *,
        text: str,
        command,
        accent: str = HOLO_ACCENT,
        width: int = 180,
        height: int = 56,
    ) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=text,
            width=width,
            height=height,
            command=command,
            fg_color=HOLO_BG_PANEL,
            hover_color=accent,
            border_color=accent,
            border_width=1,
            text_color=accent,
            font=ctk.CTkFont(family=HUD_FONT_FAMILY, size=13, weight="bold"),
        )

    def _draw_hud_grid(self, event: Optional[Any] = None) -> None:
        canvas = self._grid_canvas
        canvas.delete("hud_grid")
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w <= 1 or h <= 1:
            return
        step = 32
        for x in range(0, w, step):
            canvas.create_line(x, 0, x, h, fill=HOLO_GRID, tags="hud_grid")
        for y in range(0, h, step):
            canvas.create_line(0, y, w, y, fill=HOLO_GRID, tags="hud_grid")
        # Corner brackets for the HUD frame feel.
        bracket = 24
        for (ax, ay, bx, by) in (
            (4, 4, bracket, 4), (4, 4, 4, bracket),
            (w - 4, 4, w - bracket, 4), (w - 4, 4, w - 4, bracket),
            (4, h - 4, bracket, h - 4), (4, h - 4, 4, h - bracket),
            (w - 4, h - 4, w - bracket, h - 4), (w - 4, h - 4, w - 4, h - bracket),
        ):
            canvas.create_line(ax, ay, bx, by, fill=HOLO_ACCENT, width=2, tags="hud_grid")

    def _build_right_panel(self, parent: Any) -> None:
        right = ctk.CTkFrame(
            parent,
            corner_radius=12,
            fg_color=HOLO_BG_PANEL,
            border_width=1,
            border_color=HOLO_ACCENT_DIM,
        )
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        tabs = ctk.CTkTabview(
            right,
            fg_color=HOLO_BG_PANEL,
            segmented_button_fg_color=HOLO_BG,
            segmented_button_selected_color=HOLO_ACCENT_DIM,
            segmented_button_selected_hover_color=HOLO_ACCENT,
            segmented_button_unselected_color=HOLO_BG,
            segmented_button_unselected_hover_color=HOLO_ACCENT_DIM,
            text_color=HOLO_TEXT,
        )
        tabs.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=8, pady=8)

        agi_tab = tabs.add("Seraphina AGI")
        log_tab = tabs.add("Event Log")

        # Seraphina chat panel
        agi_tab.grid_columnconfigure(0, weight=1)
        agi_tab.grid_rowconfigure(0, weight=1)
        self.agi_response = ctk.CTkTextbox(
            agi_tab,
            fg_color=HOLO_BG,
            border_color=HOLO_ACCENT_DIM,
            border_width=1,
            text_color=HOLO_TEXT,
            font=ctk.CTkFont(family=HUD_FONT_FAMILY, size=12),
        )
        self.agi_response.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 4))

        entry_row = ctk.CTkFrame(agi_tab, fg_color="transparent")
        entry_row.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 8))
        entry_row.grid_columnconfigure(0, weight=1)
        self.agi_input = ctk.CTkEntry(
            entry_row,
            placeholder_text='e.g. "Open the gate to 3/4 inch if hopper is above 300mm"',
            fg_color=HOLO_BG,
            border_color=HOLO_ACCENT_DIM,
            text_color=HOLO_TEXT,
            placeholder_text_color=HOLO_ACCENT_DIM,
            font=ctk.CTkFont(family=HUD_FONT_FAMILY, size=12),
        )
        self.agi_input.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.agi_input.bind("<Return>", lambda _e: self.send_to_seraphina())
        self._holo_button(
            entry_row,
            text="Ask Seraphina",
            command=self.send_to_seraphina,
            accent=HOLO_ACCENT,
            width=140,
            height=32,
        ).grid(row=0, column=1)

        # Event log panel
        log_tab.grid_columnconfigure(0, weight=1)
        log_tab.grid_rowconfigure(0, weight=1)
        self.log_text = ctk.CTkTextbox(
            log_tab,
            fg_color=HOLO_BG,
            border_color=HOLO_ACCENT_DIM,
            border_width=1,
            text_color=HOLO_TEXT,
            font=ctk.CTkFont(family=HUD_FONT_FAMILY, size=12),
        )
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

    # -- Hardware ---------------------------------------------------------

    def _connect_hardware(self) -> None:
        if serial is None:
            self._log("pyserial not installed - hardware I/O disabled")
            return

        try:
            self.gate_ser = serial.Serial(GATE_PORT, SERIAL_BAUD, timeout=0.5)
            self.gate_link_lamp.set_state("ok", label="GATE LINK")
            self._log(f"Connected gate board on {GATE_PORT}")
        except Exception as exc:
            self.gate_link_lamp.set_state("alarm", label="GATE LINK FAIL")
            self._log(f"Gate board connect failed: {exc}")

        try:
            self.tele_ser = serial.Serial(TELE_PORT, SERIAL_BAUD, timeout=0.5)
            self.tele_link_lamp.set_state("ok", label="TELE LINK")
            self._log(f"Connected telescope board on {TELE_PORT}")
        except Exception as exc:
            self.tele_link_lamp.set_state("alarm", label="TELE LINK FAIL")
            self._log(f"Telescope board connect failed: {exc}")

        # Give the boards a moment to finish their reset before we issue commands.
        time.sleep(1.5)

    def write_gate(self, command: str, *, origin: str = "manual") -> bool:
        if not command:
            return False
        if self.gate_ser is None:
            self._log(f"[{origin}] gate cmd '{command}' dropped (no link)")
            return False
        try:
            self.gate_ser.write((command + "\n").encode())
            self._log(f"[{origin}] gate \u2192 {command}")
            return True
        except Exception as exc:
            self._log(f"gate write failed: {exc}")
            return False

    def write_tele(self, command: str, *, origin: str = "manual") -> bool:
        if not command:
            return False
        if self.tele_ser is None:
            self._log(f"[{origin}] tele cmd '{command}' dropped (no link)")
            return False
        try:
            self.tele_ser.write((command + "\n").encode())
            self._log(f"[{origin}] tele \u2192 {command}")
            return True
        except Exception as exc:
            self._log(f"tele write failed: {exc}")
            return False

    # -- Operator actions -------------------------------------------------

    def _on_preset_change(self, value: str) -> None:
        if value in GATE_PRESETS:
            self.current_preset = value

    def open_gate(self) -> None:
        preset = self.preset_combo.get()
        steps = GATE_PRESETS.get(preset)
        if steps is None:
            self._log(f"Unknown preset '{preset}'")
            return
        if self.write_gate(f"OPEN {steps}", origin="manual"):
            self.current_preset = preset
            # Visual feedback before sensors confirm: assume linear preset map.
            ordered = list(GATE_PRESETS.values())
            largest = max(ordered)
            self.valve_open_pct = 100.0 * steps / largest if largest else 0.0
            self.gate_lamp.set_state("warn", label=f"GATE OPEN {preset}")

    def close_gate(self) -> None:
        if self.write_gate("CLOSE", origin="manual"):
            self.valve_open_pct = 0.0
            self.gate_lamp.set_state("ok", label="GATE CLOSED")

    def set_pump(self, on: bool) -> None:
        cmd = "PUMP ON" if on else "PUMP OFF"
        if self.write_gate(cmd, origin="manual"):
            self.pump_on = on
            self.pump_lamp.set_state("info" if on else "off", label="PUMP ON" if on else "PUMP OFF")

    def send_to_seraphina(self) -> None:
        prompt = self.agi_input.get().strip()
        if not prompt:
            return
        self.agi_input.delete(0, "end")
        self._append_chat(f"> {prompt}")
        self._log(f"Seraphina \u2190 {prompt}")
        threading.Thread(target=self._seraphina_worker, args=(prompt,), daemon=True).start()

    def _seraphina_worker(self, prompt: str) -> None:
        reply = self.seraphina.ask(prompt)
        self.root.after(0, lambda: self._append_chat(f"Seraphina: {reply}\n"))

        # Lightweight intent shim: still let plain-language commands move the rig
        # even when Seraphina has no native tool-calling surface.
        lowered = prompt.lower()
        if "close" in lowered and "gate" in lowered:
            self.root.after(0, self.close_gate)
        elif "open" in lowered and "gate" in lowered:
            for preset in GATE_PRESETS:
                if preset.lower().strip('"') in lowered:
                    self.root.after(0, lambda p=preset: (self.preset_combo.set(p), self.open_gate()))
                    break
            else:
                self.root.after(0, self.open_gate)
        elif "pump" in lowered and "on" in lowered:
            self.root.after(0, lambda: self.set_pump(True))
        elif "pump" in lowered and "off" in lowered:
            self.root.after(0, lambda: self.set_pump(False))
        elif "tele" in lowered and "up" in lowered:
            self.root.after(0, lambda: self.write_tele("TELE_UP", origin="seraphina"))
        elif "tele" in lowered and "down" in lowered:
            self.root.after(0, lambda: self.write_tele("TELE_DOWN", origin="seraphina"))

    # -- Sensor + UI loops ------------------------------------------------

    def _start_sensor_thread(self) -> None:
        threading.Thread(target=self._sensor_loop, daemon=True).start()

    def _sensor_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                if self.gate_ser is not None and self.gate_ser.in_waiting:
                    line = self.gate_ser.readline().decode(errors="replace").strip()
                    if line.startswith("{"):
                        try:
                            payload = json.loads(line)
                        except json.JSONDecodeError:
                            self._log_threadsafe(f"bad JSON: {line[:80]}")
                        else:
                            decision = self.hopper_core.on_sensor_payload(payload)
                            self.root.after(0, lambda d=decision: self._on_policy_decision(d))
                    elif line:
                        self._log_threadsafe(f"gate: {line}")
            except Exception as exc:  # pragma: no cover - hardware noise
                self._log_threadsafe(f"sensor read error: {exc}")
            time.sleep(SENSOR_POLL_INTERVAL_S)

    def _refresh_ui(self) -> None:
        state = self.state_store.snapshot()

        # Level gauge: report distance in mm; warn/alarm coloring.
        level = state.ultrasonic_mm
        if level is None or state.is_stale():
            self.level_gauge.set_value(None)
        else:
            color = HOLO_ACCENT
            if level >= LEVEL_LOW_WARN_MM:
                color = HOLO_ALARM
            elif level >= LEVEL_LOW_WARN_MM * 0.75:
                color = HOLO_WARN
            self.level_gauge.set_value(float(level), color=color)

        # Valve gauge mirrors the most recent operator/policy command.
        if state.gate_open:
            self.valve_gauge.set_value(max(self.valve_open_pct, 1.0), color=HOLO_OK)
            self.gate_lamp.set_state("warn", label=f"GATE OPEN {self.current_preset}")
        else:
            self.valve_gauge.set_value(0.0, color=HOLO_MUTED)
            self.gate_lamp.set_state("ok", label="GATE CLOSED")

        # Annunciator lamps
        if state.dust_detected:
            self.dust_lamp.set_state("alarm", label="DUST ONLY")
        else:
            self.dust_lamp.set_state("ok", label="MATERIAL OK")

        if state.is_stale():
            self.flow_lamp.set_state("warn", label="FLOW STALE")
        elif state.pir_motion:
            self.flow_lamp.set_state("ok", label="FLOW DETECTED")
        else:
            self.flow_lamp.set_state("off", label="FLOW IDLE")

        # Status bar summary
        bits = []
        if state.board_id and state.board_id != "UNKNOWN":
            bits.append(f"board={state.board_id}")
        if level is not None:
            bits.append(f"level={level}mm")
        bits.append(f"valve={self.valve_open_pct:.0f}%")
        bits.append(f"pump={'ON' if self.pump_on else 'OFF'}")
        bits.append(f"agi={self.seraphina.backend}")
        self.status_bar.configure(text="  |  ".join(bits))

        self.root.after(UI_REFRESH_INTERVAL_MS, self._refresh_ui)

    def _on_policy_decision(self, decision: PolicyDecision) -> None:
        self.policy_text.configure(state="normal")
        self.policy_text.delete("1.0", "end")
        if decision.has_actions:
            if decision.gate_command:
                self.policy_text.insert("end", f"gate \u2192 {decision.gate_command}\n")
            if decision.tele_command:
                self.policy_text.insert("end", f"tele \u2192 {decision.tele_command}\n")
            if decision.alert:
                self.policy_text.insert("end", f"alert: {decision.alert}\n")
        else:
            self.policy_text.insert("end", "all clear\n")
        self.policy_text.configure(state="disabled")

        if decision.gate_command == "CLOSE":
            # Reflect auto-close visually.
            self.valve_open_pct = 0.0

    def _tick_clock(self) -> None:
        self.clock_label.configure(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.root.after(1000, self._tick_clock)

    # -- Logging ----------------------------------------------------------

    def _log(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {message}\n")
        self.log_text.see("end")

    def _log_threadsafe(self, message: str) -> None:
        self.root.after(0, lambda m=message: self._log(m))

    def _append_chat(self, message: str) -> None:
        self.agi_response.insert("end", message + "\n")
        self.agi_response.see("end")

    # -- Lifecycle --------------------------------------------------------

    def run(self) -> None:
        try:
            self.root.mainloop()
        finally:
            self._stop_event.set()
            for ser in (self.gate_ser, self.tele_ser):
                try:
                    if ser is not None:
                        ser.close()
                except Exception:
                    pass


def main() -> None:
    SeraphinaCockpitGUI().run()


if __name__ == "__main__":
    main()
