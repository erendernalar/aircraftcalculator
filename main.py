import os
import sys

from PyQt5.QtGui import QColor, QIcon, QPalette
from PyQt5.QtWidgets import QApplication

from app import MainWindow, DARK_STYLE
from theme import _BG, _SURFACE, _OVERLAY, _TEXT, _SUBTEXT, _MUTED, _ACCENT, _RED

def _app_icon() -> QIcon:
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    # Prefer ICO on Windows (supports all taskbar/title sizes), PNG elsewhere
    if sys.platform == 'win32':
        path = os.path.join(base, 'assets', 'logo.ico')
    else:
        path = os.path.join(base, 'assets', 'logo.png')
    if not os.path.exists(path):
        path = os.path.join(base, 'assets', 'logo.png')
    return QIcon(path)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setWindowIcon(_app_icon())

    c = QColor
    palette = QPalette()
    palette.setColor(QPalette.Window,          c(_BG))
    palette.setColor(QPalette.WindowText,      c(_TEXT))
    palette.setColor(QPalette.Base,            c(_SURFACE))
    palette.setColor(QPalette.AlternateBase,   c(_OVERLAY))
    palette.setColor(QPalette.ToolTipBase,     c(_OVERLAY))
    palette.setColor(QPalette.ToolTipText,     c(_TEXT))
    palette.setColor(QPalette.Text,            c(_TEXT))
    palette.setColor(QPalette.Button,          c(_OVERLAY))
    palette.setColor(QPalette.ButtonText,      c(_TEXT))
    palette.setColor(QPalette.BrightText,      c(_RED))
    palette.setColor(QPalette.Link,            c(_ACCENT))
    palette.setColor(QPalette.Highlight,       c(_ACCENT))
    palette.setColor(QPalette.HighlightedText, c(_BG))
    palette.setColor(QPalette.Disabled, QPalette.Text,       c(_MUTED))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, c(_MUTED))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, c(_MUTED))
    app.setPalette(palette)
    app.setStyleSheet(DARK_STYLE)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
