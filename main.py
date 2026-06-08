import sys

from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication

from app import MainWindow, DARK_STYLE


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    palette = QPalette()
    c = lambda h: QColor(h)
    palette.setColor(QPalette.Window,          c('#1E1E2E'))
    palette.setColor(QPalette.WindowText,      c('#CDD6F4'))
    palette.setColor(QPalette.Base,            c('#252535'))
    palette.setColor(QPalette.AlternateBase,   c('#313244'))
    palette.setColor(QPalette.ToolTipBase,     c('#313244'))
    palette.setColor(QPalette.ToolTipText,     c('#CDD6F4'))
    palette.setColor(QPalette.Text,            c('#CDD6F4'))
    palette.setColor(QPalette.Button,          c('#313244'))
    palette.setColor(QPalette.ButtonText,      c('#CDD6F4'))
    palette.setColor(QPalette.BrightText,      c('#F38BA8'))
    palette.setColor(QPalette.Link,            c('#89B4FA'))
    palette.setColor(QPalette.Highlight,       c('#89B4FA'))
    palette.setColor(QPalette.HighlightedText, c('#1E1E2E'))
    palette.setColor(QPalette.Disabled, QPalette.Text,       c('#6C7086'))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, c('#6C7086'))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, c('#6C7086'))
    app.setPalette(palette)
    app.setStyleSheet(DARK_STYLE)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
