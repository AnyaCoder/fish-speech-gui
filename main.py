import signal
import sys
import time

import qdarktheme
from PyQt6 import QtCore, QtGui, QtWidgets

from fish.config import application_path, config
from fish.gui import MainWindow


class SplashScreen(QtWidgets.QSplashScreen):
    def __init__(self):
        pixmap = QtGui.QPixmap(str(application_path / "assets" / "splash.png"))
        super().__init__(pixmap)
        self.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint)


def main():
    t1 = time.time()
    qdarktheme.enable_hi_dpi()
    app = QtWidgets.QApplication(sys.argv)
    splash = SplashScreen()
    splash.show()
    QtWidgets.QApplication.processEvents()  # assure display splash
    window = MainWindow()
    # qdarktheme.setup_theme(config.theme)
    # Make output to demonstrate real-time capture

    print("This laziman message is redirected to the console.", file=sys.stderr)
    splash.finish(window)
    # run
    window.show()
    t2 = time.time()
    print(f"AnyaCoder application started..., elapsed: {t2 - t1}s", file=sys.stdout)
    app.exec()


# handle Ctrl+C
signal.signal(signal.SIGINT, signal.SIG_DFL)

if __name__ == "__main__":
    main()
