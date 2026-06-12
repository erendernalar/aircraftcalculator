import sys

from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication

from app import MainWindow, DARK_STYLE
from theme import _BG, _SURFACE, _OVERLAY, _TEXT, _SUBTEXT, _MUTED, _ACCENT, _RED


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

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
