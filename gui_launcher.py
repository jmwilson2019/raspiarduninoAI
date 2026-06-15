#!/usr/bin/env python3
"""Safe launcher for the optional GUI entrypoint."""

from __future__ import annotations


def main() -> int:
    """Launch the GUI and provide a clear error if GUI extras are missing."""
    try:
        from gui import main as gui_main
    except ImportError as exc:
        print("Error: GUI dependencies are missing.")
        print("Install them with one of:")
        print('  pip install "raspiarduninoai[gui]"')
        print('  pip install PyQt5 pyqtgraph')
        print(f"\nOriginal import error: {exc}")
        return 1

    gui_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
