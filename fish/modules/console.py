import sys
import threading

from loguru import logger
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QDockWidget,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ConsoleStream(QObject):
    new_message = pyqtSignal(str)

    def __init__(self):
        super().__init__()

    def write(self, message):
        self.new_message.emit(message)

    def flush(self):
        pass


class ConsoleWidget(QTextEdit):
    def __init__(self, max_lines=1000):
        super().__init__()
        self.setReadOnly(True)
        self.setStyleSheet(
            """
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: 'Courier New', monospace;
                font-size: 15px;
                border: none;
            }
        """
        )
        self.max_lines = max_lines

    def update_console(self, text, color="white", newline=False):
        cursor = self.textCursor()
        format = QTextCharFormat()
        format.setForeground(QColor(color))
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text + ("\n" if newline else ""), format)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        self.queue_clear()

    def queue_clear(self):
        while self.document().blockCount() > self.max_lines:
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()  # 删除换行符

    def clear_console(self):
        self.clear()


class ConsoleDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Console", parent)
        self.console_widget = ConsoleWidget()
        self.setMinimumWidth(400)
        self.clear_button = QPushButton("Empty Console")
        self.clear_button.clicked.connect(self.console_widget.clear_console)

        layout = QVBoxLayout()
        layout.addWidget(self.clear_button)
        layout.addWidget(self.console_widget)

        container = QWidget()
        container.setLayout(layout)
        self.setWidget(container)

        self.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.setVisible(True)


class ConsoleWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sample")
        self.setGeometry(100, 100, 800, 600)

        self.console_dock = ConsoleDock(self)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.console_dock)

        self.stdout_stream = ConsoleStream()
        self.stdout_stream.new_message.connect(
            lambda msg: self.update_console(msg, "white")
        )
        sys.stdout = self.stdout_stream

        self.start_background_thread()

    def update_console(self, message: str, color: str):
        self.console_dock.console_widget.update_console(message, color)

    def start_background_thread(self):
        self.worker_thread = threading.Thread(target=self.simulate_output, daemon=True)
        self.worker_thread.start()

    def simulate_output(self):
        import time

        print("Are you ok?")
        for i in range(200):
            self.update_console(f"Processing task {i+1}/200...", "white")
            time.sleep(0.1)
        self.update_console("Mission complete!", "red")
        raise Exception("Simulation error occurred")

    def keyPressEvent(self, event):
        if (
            event.key() == Qt.Key.Key_P
            and event.modifiers() == Qt.KeyboardModifier.ControlModifier
        ):
            self.console_dock.setVisible(not self.console_dock.isVisible())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ConsoleWindow()
    window.show()
    sys.exit(app.exec())
