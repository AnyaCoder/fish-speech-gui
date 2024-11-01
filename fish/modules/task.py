from PyQt6.QtCore import QMutex, QMutexLocker
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QFileDialog,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QWidget,
)

from fish.modules.console import ConsoleWidget
from fish.modules.globals import STOP_BUTTON_QSS
from fish.modules.worker import SubprocessWorker
from fish.utils.i18n import _t


class BaseWidgetMixin(QWidget):
    def __init__(self, name="Base"):
        super().__init__()
        self.name = name
        self.input_dir = QLineEdit()
        self.output_dir = QLineEdit()
        self.input_dir.setPlaceholderText(f"{name}: Select the input directory")
        self.output_dir.setPlaceholderText(f"{name}: Select the output directory")

    def browse_input_dir(self):
        self._browse_directory(self.input_dir, "Select Input Directory")

    def browse_output_dir(self):
        self._browse_directory(self.output_dir, "Select Output Directory")

    def _browse_directory(self, line_edit: QLineEdit, title: str):
        dir_path = QFileDialog.getExistingDirectory(self, title)
        if dir_path:
            line_edit.setText(dir_path)


class TaskManagerMixin(BaseWidgetMixin):
    def __init__(self, console_widget: ConsoleWidget, name="Base"):
        super().__init__(name)
        self.worker = None
        self.mutex = QMutex()
        self.console_widget = console_widget
        self.start_button = QPushButton(f"Start {name}")
        self.stop_button = QPushButton(f"Stop {name}")
        self.stop_button.setStyleSheet(STOP_BUTTON_QSS)
        self.stop_button.setEnabled(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)

    def start_task(self, args):
        with QMutexLocker(self.mutex):
            if self.worker and self.worker.isRunning():
                QMessageBox.warning(
                    self, f"Task Running", f"A {self.name} task is already running."
                )
                return False

            self.worker = SubprocessWorker(args)

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.worker.finished_signal.connect(self.on_task_finished)
        self.worker.output_signal.connect(self.on_task_update)
        self.worker.start()
        return True

    def stop_task(self):
        with QMutexLocker(self.mutex):
            if self.worker and self.worker.isRunning():
                self.worker.stop()
                QMessageBox.information(
                    self, f"Task Stopped", f"The {self.name} task has been stopped."
                )
                return True
            else:
                QMessageBox.warning(
                    self,
                    "No Running Task",
                    f"There is no running {self.name} task to stop.",
                )
                return False

    def on_task_update(self, message, is_progress_update, progress):
        if is_progress_update:
            cursor = self.console_widget.textCursor()
            cursor.movePosition(
                QTextCursor.MoveOperation.StartOfLine, QTextCursor.MoveMode.KeepAnchor
            )
            cursor.removeSelectedText()
            self.console_widget.update_console(message, "yellow", newline=False)
            self.progress_bar.setValue(int(progress))
        else:
            self.console_widget.update_console(message, "white", newline=True)

    def on_task_finished(self, message):
        QMessageBox.information(self, f"Task {self.name} Completed", message)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
