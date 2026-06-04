#!/usr/bin/env python3
"""
Visualization widgets for raspiarduninoAI.

Includes:
- Ultrasonic beam visualization
- Power monitoring displays
"""

from __future__ import annotations

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont
import pyqtgraph as pg


# Holographic color scheme
HOLO_CYAN = "#00FFFF"
HOLO_BLUE = "#0080FF"
HOLO_PURPLE = "#8000FF"
HOLO_GREEN = "#00FF80"
HOLO_RED = "#FF0040"
HOLO_BG = "#0A0A1A"
HOLO_PANEL = "#151530"
HOLO_TEXT = "#E0E0FF"


class UltrasonicBeamWidget(QWidget):
    """Visualizes ultrasonic sensor beam and detected distance."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.distance_mm = 0
        self.max_distance_mm = 4000
        self.detecting = False
        self.setMinimumSize(250, 200)

    def set_distance(self, distance_mm: float):
        """Update the distance reading."""
        self.distance_mm = distance_mm
        self.detecting = True
        self.update()

    def clear(self):
        """Clear the visualization."""
        self.detecting = False
        self.update()

    def paintEvent(self, event):
        """Draw the ultrasonic beam visualization."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background
        painter.fillRect(self.rect(), QColor(HOLO_BG))

        width = self.width()
        height = self.height()

        # Sensor position (top center)
        sensor_x = width // 2
        sensor_y = 20

        # Draw sensor box
        painter.setPen(QPen(QColor(HOLO_CYAN), 2))
        painter.setBrush(QBrush(QColor(HOLO_PANEL)))
        painter.drawRect(sensor_x - 15, sensor_y - 10, 30, 20)

        if self.detecting:
            # Calculate beam spread
            beam_width = 60  # degrees
            beam_distance = min(self.distance_mm, self.max_distance_mm)

            # Normalize distance to widget height
            max_beam_length = height - sensor_y - 20
            beam_length = (beam_distance / self.max_distance_mm) * max_beam_length

            # Draw beam cone
            beam_color = QColor(HOLO_CYAN)
            beam_color.setAlpha(50)
            painter.setBrush(QBrush(beam_color))
            painter.setPen(QPen(QColor(HOLO_CYAN), 1))

            # Calculate beam end points
            import math
            half_angle = math.radians(beam_width / 2)
            left_x = sensor_x - int(beam_length * math.tan(half_angle))
            right_x = sensor_x + int(beam_length * math.tan(half_angle))
            beam_end_y = sensor_y + int(beam_length)

            # Draw beam triangle
            from PyQt5.QtCore import QPoint
            points = [
                QPoint(sensor_x, sensor_y + 10),
                QPoint(left_x, beam_end_y),
                QPoint(right_x, beam_end_y),
            ]
            from PyQt5.QtGui import QPolygon
            painter.drawPolygon(QPolygon(points))

            # Draw detection point
            if beam_distance < self.max_distance_mm:
                painter.setPen(QPen(QColor(HOLO_GREEN), 3))
                painter.setBrush(QBrush(QColor(HOLO_GREEN)))
                painter.drawEllipse(sensor_x - 5, beam_end_y - 5, 10, 10)

                # Draw distance line
                painter.setPen(QPen(QColor(HOLO_GREEN), 1, Qt.DashLine))
                painter.drawLine(sensor_x, sensor_y + 10, sensor_x, beam_end_y)

            # Distance text
            painter.setPen(QPen(QColor(HOLO_TEXT)))
            font = QFont("Courier New", 12, QFont.Bold)
            painter.setFont(font)

            if beam_distance < 1000:
                text = f"{int(beam_distance)} mm"
            else:
                text = f"{beam_distance / 1000:.2f} m"

            painter.drawText(10, height - 30, text)

            # Status
            status = "DETECTING" if beam_distance < self.max_distance_mm else "NO ECHO"
            painter.setPen(QPen(QColor(HOLO_CYAN)))
            painter.drawText(10, height - 10, status)

        else:
            # Draw idle state
            painter.setPen(QPen(QColor(HOLO_TEXT)))
            font = QFont("Courier New", 10)
            painter.setFont(font)
            painter.drawText(
                self.rect(),
                Qt.AlignCenter,
                "Ultrasonic Idle"
            )


class PowerMonitorWidget(QWidget):
    """Displays real-time power monitoring."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.voltage = 0.0
        self.current = 0.0
        self.voltage_warning = 11.0
        self.current_warning = 5.0

        layout = QVBoxLayout(self)

        # Title
        title = QLabel("⚡ Power Monitor")
        title.setStyleSheet(f"color: {HOLO_CYAN}; font-size: 16px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Voltage gauge
        self.voltage_plot = pg.PlotWidget()
        self.voltage_plot.setBackground(HOLO_BG)
        self.voltage_plot.setTitle("Voltage (V)", color=HOLO_CYAN)
        self.voltage_plot.setYRange(0, 15)
        self.voltage_plot.setMaximumHeight(120)
        self.voltage_data = []
        self.voltage_curve = self.voltage_plot.plot(
            pen=pg.mkPen(color=HOLO_GREEN, width=2)
        )
        layout.addWidget(self.voltage_plot)

        # Current gauge
        self.current_plot = pg.PlotWidget()
        self.current_plot.setBackground(HOLO_BG)
        self.current_plot.setTitle("Current (A)", color=HOLO_CYAN)
        self.current_plot.setYRange(0, 10)
        self.current_plot.setMaximumHeight(120)
        self.current_data = []
        self.current_curve = self.current_plot.plot(
            pen=pg.mkPen(color=HOLO_BLUE, width=2)
        )
        layout.addWidget(self.current_plot)

        # Power display
        self.power_label = QLabel("Power: 0.0 W")
        self.power_label.setStyleSheet(f"color: {HOLO_TEXT}; font-size: 14px;")
        self.power_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.power_label)

        # Warning lines
        self.voltage_warning_line = pg.InfiniteLine(
            pos=self.voltage_warning,
            angle=0,
            pen=pg.mkPen(color=HOLO_RED, width=2, style=Qt.DashLine)
        )
        self.voltage_plot.addItem(self.voltage_warning_line)

        self.current_warning_line = pg.InfiniteLine(
            pos=self.current_warning,
            angle=0,
            pen=pg.mkPen(color=HOLO_RED, width=2, style=Qt.DashLine)
        )
        self.current_plot.addItem(self.current_warning_line)

    def update_readings(self, voltage: float, current: float):
        """Update voltage and current readings."""
        self.voltage = voltage
        self.current = current

        # Update data buffers (keep last 100 points)
        self.voltage_data.append(voltage)
        if len(self.voltage_data) > 100:
            self.voltage_data.pop(0)

        self.current_data.append(current)
        if len(self.current_data) > 100:
            self.current_data.pop(0)

        # Update plots
        self.voltage_curve.setData(self.voltage_data)
        self.current_curve.setData(self.current_data)

        # Update power label
        power = voltage * current
        self.power_label.setText(f"Power: {power:.2f} W")

        # Change color if warning threshold exceeded
        if voltage < self.voltage_warning:
            self.power_label.setStyleSheet(f"color: {HOLO_RED}; font-size: 14px; font-weight: bold;")
        elif current > self.current_warning:
            self.power_label.setStyleSheet(f"color: {HOLO_RED}; font-size: 14px; font-weight: bold;")
        else:
            self.power_label.setStyleSheet(f"color: {HOLO_TEXT}; font-size: 14px;")

    def set_warning_thresholds(self, voltage_warning: float, current_warning: float):
        """Update warning threshold lines."""
        self.voltage_warning = voltage_warning
        self.current_warning = current_warning
        self.voltage_warning_line.setPos(voltage_warning)
        self.current_warning_line.setPos(current_warning)
