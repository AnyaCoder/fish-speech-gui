import signal
import sys

import qdarktheme
from PyQt6 import QtWidgets

from fish.config import config
from fish.gui import MainWindow


def main():
    qdarktheme.enable_hi_dpi()
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    qdarktheme.setup_theme(config.theme)

    # run
    window.show()
    app.exec()


# handle Ctrl+C
signal.signal(signal.SIGINT, signal.SIG_DFL)

if __name__ == "__main__":
    main()
