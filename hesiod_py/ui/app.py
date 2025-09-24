"""Application bootstrap helpers for the Hesiod UI."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence

from PySide6 import QtWidgets

from .main_window import MainWindow

__all__ = ["launch", "main"]


def _ensure_application(argv: Sequence[str] | None = None) -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is not None:
        return app
    argv = list(argv or sys.argv)
    return QtWidgets.QApplication(argv)


def launch(*, offscreen: bool = False, argv: Sequence[str] | None = None) -> int:
    """Launch the Hesiod UI and block until the window closes."""

    if offscreen:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = _ensure_application(argv)
    window = MainWindow()
    window.show()
    return app.exec()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hesiod Python UI")
    parser.add_argument(
        "--offscreen",
        action="store_true",
        help="Use the offscreen Qt platform plugin (useful for testing environments).",
    )
    args = parser.parse_args(argv)
    return launch(offscreen=args.offscreen, argv=argv)


if __name__ == "__main__":  # pragma: no cover - manual invocation entry point
    raise SystemExit(main())
