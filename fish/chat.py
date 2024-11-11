import os
import signal
import sys
import tempfile

from PyQt6.QtCore import Qt, QTime, QUrl
from PyQt6.QtGui import QFont, QFontMetrics
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fish.config import config, save_config
from fish.modules.worker import AudioWorker, logger
from fish.utils.i18n import _t


class SettingsDialog(QDialog):
    def __init__(
        self,
        current_api_url: str = None,
        current_system_prompt: str = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(_t("SettingsDialog.title"))
        self.setModal(True)
        self.setMinimumSize(400, 200)

        # Set the current API URL and System Prompt if passed
        self.chat_api_url = current_api_url or ""
        self.system_prompt = current_system_prompt or ""

        layout = QVBoxLayout()

        # Create a form layout for the input fields
        form_layout = QFormLayout()

        # API URL input
        self.chat_api_input = QLineEdit(self.chat_api_url)
        form_layout.addRow(_t("SettingsDialog.chat_api_url"), self.chat_api_input)

        # System Prompt input
        layout.addWidget(QLabel(_t("SettingsDialog.sys_prompt")))
        self.system_prompt_input = QTextEdit()
        self.system_prompt_input.setPlainText(self.system_prompt.strip())
        layout.addWidget(self.system_prompt_input)

        # Create buttons
        save_button = QPushButton(_t("SettingsDialog.save_btn"))
        cancel_button = QPushButton(_t("SettingsDialog.cancel_btn"))

        save_button.clicked.connect(self.save_settings)
        cancel_button.clicked.connect(self.reject)

        # Add form layout and buttons to the main layout
        layout.addLayout(form_layout)
        button_layout = QHBoxLayout()

        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def save_settings(self):
        # Save the API URL and System Prompt entered by the user
        self.chat_api_url = self.chat_api_input.text().strip()
        self.system_prompt = self.system_prompt_input.toPlainText().strip()

        if self.chat_api_url and self.system_prompt:  # Ensure both fields are not empty
            self.accept()
        else:
            QMessageBox.warning(
                self, "Invalid", "Input non-empty valid API URL and System Prompt"
            )


class MessageBubble(QWidget):
    player = QMediaPlayer()  # Class-level static player instance
    audio_output = QAudioOutput()
    is_connected = False

    def __init__(
        self,
        text,
        is_sender=True,
        is_voice=False,
        is_voice_clickable=False,
        audio_file=None,
        voice_duration=None,
        timestamp=None,
        parent=None,
    ):
        super().__init__(parent)
        self.text = text
        self.is_sender = is_sender
        self.is_voice = is_voice
        self.is_voice_clickable = is_voice_clickable
        self.voice_duration = voice_duration
        self.timestamp = (
            timestamp if timestamp else QTime.currentTime().toString("HH:mm:ss")
        )
        self.audio_file = audio_file

        self.initUI()

    def initUI(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(2)

        bubble_layout = QHBoxLayout()
        bubble_layout.setContentsMargins(0, 0, 0, 0)
        bubble_layout.setSpacing(5)

        if self.is_sender:
            bubble_layout.addStretch()

        bubble_color = "#DCF8C6" if self.is_sender else "#FFFFFF"

        if self.is_voice:
            self.msg = QPushButton()
            self.msg.setText(f"🔊 {self.voice_duration:.1f}s")
            self.msg.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {bubble_color};
                    border-radius: 15px;
                    padding: 10px;
                    border: 1px solid #E0E0E0;
                }}
                QPushButton:hover {{
                    background-color: {"#C6E5F7" if self.is_sender else "#F1F1F1"};
                    border: 2px solid #E0E0E0;
                }}
                """
            )
            self.msg.setEnabled(self.is_voice_clickable)
            self.msg.clicked.connect(self.toggle_playback)
            MessageBubble.player.setAudioOutput(MessageBubble.audio_output)
        else:
            self.msg = QLabel(self.text)
            self.msg.setWordWrap(True)
            self.msg.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            self.msg.setStyleSheet(
                f"""
                background-color: {bubble_color};
                border: 1px solid #E0E0E0;
                border-radius: 15px;
                padding: 10px;
                font-size: 14px;
                color: {"#000000" if self.is_sender else "#333333"};
                """
            )

        self.msg.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.msg.setMaximumWidth(300)
        bubble_layout.addWidget(self.msg)

        if not self.is_sender:
            bubble_layout.addStretch()

        main_layout.addLayout(bubble_layout)

        time_label = QLabel(self.timestamp)
        time_label.setFont(QFont("Arial", 8))
        time_label.setStyleSheet("color: gray;")

        if self.is_sender:
            time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            main_layout.addWidget(time_label, alignment=Qt.AlignmentFlag.AlignRight)
        else:
            time_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            main_layout.addWidget(time_label, alignment=Qt.AlignmentFlag.AlignLeft)

        self.setLayout(main_layout)

        # Connect the playbackStateChanged signal only once
        if MessageBubble.is_connected is False:
            MessageBubble.player.playbackStateChanged.connect(self.on_state_changed)
            MessageBubble.is_connected = True

    def get_dynamic_width(self, parent_width):
        max_width_from_parent = int(parent_width * 0.7)
        font_metrics = QFontMetrics(self.msg.font())
        text_width = font_metrics.horizontalAdvance(self.text) + 30
        return min(max_width_from_parent, text_width)

    def toggle_playback(self):
        if (
            MessageBubble.player.playbackState()
            == QMediaPlayer.PlaybackState.StoppedState
        ):
            # Ensure the file exists before trying to play it
            if os.path.exists(self.audio_file):
                MessageBubble.player.setSource(QUrl.fromLocalFile(self.audio_file))
                MessageBubble.player.setPosition(0)
                MessageBubble.player.play()
            else:
                logger.error(f"Audio file does not exist: {self.audio_file}")
        else:
            MessageBubble.player.stop()

    def on_state_changed(self, state):
        logger.info(f"Playback state changed: {state}")
        # You can handle UI updates based on state if needed
        if state == QMediaPlayer.PlaybackState.StoppedState:
            logger.info("Playback stopped.")
        elif state == QMediaPlayer.PlaybackState.PlayingState:
            logger.info("Playback started.")


RECORD_START_QSS = (
    """
QPushButton {
    padding: 8px;
    border-radius: 5px;
    border: 1px solid #CCCCCC;
    background-color: #1AB4F6FF;
    color: white;
    font-weight: bold;
}
"""
    + """
QPushButton:hover {
    background-color: #5CBEFF;
    border: 1px solid #5FBFFF;
}
"""
)

RECORD_STOP_QSS = """
QPushButton {
    padding: 8px;
    border-radius: 5px;
    border: 1px solid #CCCCCC;
    background-color: #FF4D4D;
    color: white;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #FF0000;
    border: 1px solid #FF0000;
}
"""

RECORD_CANCEL_QSS = (
    """
QPushButton {
    padding: 8px;
    border-radius: 5px;
    background-color: #FF4D4D;
    color: white;
    font-weight: bold;
}
"""
    + """
QPushButton:hover {
    background-color: #FF0000;
}
"""
)

INPUT_FIELD_QSS = """
padding: 8px;
border-radius: 5px;
border: 1px solid #CCCCCC;
background-color: #FFFFFF;
"""

SEND_BUTTON_QSS = (
    """
QPushButton {
    padding: 8px;
    border-radius: 5px;
    background-color: #00C300;
    color: white;
    font-weight: bold;
}
"""
    + """
QPushButton:hover {
    background-color: #009900;
}
"""
)

CLEAN_QSS = (
    """
QPushButton {
    padding: 8px;
    border-radius: 5px;
    background-color: #FF4D4D;
    color: white;
    font-weight: bold;
}
"""
    + """
QPushButton:hover {
    background-color: #FF0000;
}
"""
)


class ChatWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(_t("ChatWidget.title"))
        self.setMinimumSize(400, 600)

        self.voice_mode_enabled = False  # Voice mode flag
        self.audio_files = []
        self.chat_api_url = config.chat_api_url
        self.system_prompt = config.system_prompt
        self.initUI()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)  # Main layout spacing

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("border: none;")
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_layout.setSpacing(10)
        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area)

        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(5, 5, 5, 5)
        input_layout.setSpacing(5)

        # Voice mode button
        self.voice_mode_button = QPushButton("🎤")
        self.voice_mode_button.setStyleSheet(RECORD_START_QSS)
        self.voice_mode_button.clicked.connect(self.toggle_voice_mode)

        self.cancel_button = QPushButton(_t("ChatWidget.cancel_btn"))
        self.cancel_button.setStyleSheet(RECORD_CANCEL_QSS)
        self.cancel_button.clicked.connect(self.cancel_recording)
        self.cancel_button.setVisible(False)  # Initially hidden
        input_layout.addWidget(self.cancel_button)

        # Text mode input
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(_t("ChatWidget.placeholder"))
        self.input_field.setStyleSheet(INPUT_FIELD_QSS)

        self.send_button = QPushButton(_t("ChatWidget.send_btn"))
        self.send_button.clicked.connect(self.send_message)
        self.send_button.setStyleSheet(SEND_BUTTON_QSS)

        self.clear_button = QPushButton(_t("ChatWidget.clear_btn"))
        self.clear_button.clicked.connect(self.clear_messages)
        self.clear_button.setStyleSheet(CLEAN_QSS)

        input_layout.addWidget(self.voice_mode_button)
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_button)
        input_layout.addWidget(self.clear_button)
        main_layout.addLayout(input_layout)
        # Add the settings button as an overlay in the top-right corner
        self.settings_button = QPushButton()
        self.settings_button.setText("⚙️")  # Set your gear icon here
        # self.settings_button.setStyleSheet("background: transparent; border: none;")
        self.settings_button.setFixedSize(32, 32)  # Adjust size as needed
        self.settings_button.clicked.connect(self.open_settings)

        # Position the settings button at the top-right corner as an overlay
        self.settings_button.setParent(self)
        self.settings_button.move(
            self.width() - 60, 10
        )  # Position with padding from the edge

    def open_settings(self):
        # Open the settings dialog
        settings_dialog = SettingsDialog(self.chat_api_url, self.system_prompt, self)
        if settings_dialog.exec() == QDialog.DialogCode.Accepted:
            # Update the stored API URL after the dialog is closed
            config.chat_api_url = self.chat_api_url = settings_dialog.chat_api_url
            config.system_prompt = self.system_prompt = settings_dialog.system_prompt
            save_config()
            # Close the dialog on save
            QMessageBox.information(
                self,
                "Done",
                f"Chat API is saved as: \n{self.chat_api_url}\n\n"
                + f"System Prompt is saved as: \n{self.system_prompt}",
            )

    def toggle_voice_mode(self):
        self.voice_mode_enabled = not self.voice_mode_enabled
        if self.voice_mode_enabled:
            self.voice_mode_button.setText("🛑")
            self.voice_mode_button.setStyleSheet(RECORD_STOP_QSS)
            self.start_recording()
        else:
            self.voice_mode_button.setText("🎤")
            self.voice_mode_button.setStyleSheet(RECORD_START_QSS)
            self.stop_recording()

    def start_recording(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            self.temp_wavfile = temp_file.name
        self.audio_worker = AudioWorker(
            save_as_file=True, output_file=self.temp_wavfile
        )
        self.audio_worker.audio_data_signal.connect(self.on_recording)
        self.audio_worker.start()
        logger.info("start recording")

        self.input_field.setDisabled(True)
        self.record_duration = 0
        self.input_field.setText(_t("ChatWidget.recording").format(dur=0))
        self.cancel_button.setVisible(True)  # Show the cancel button

    def stop_recording(self):
        self.audio_worker.stop()
        logger.info("stop recording")
        self.audio_files.append(self.temp_wavfile)
        self.send_message(audio=self.temp_wavfile)
        self.input_field.setDisabled(False)
        self.input_field.setText("")
        self.cancel_button.setVisible(False)  # Hide cancel button

    def cancel_recording(self):
        self.audio_worker.stop()  # Stop the recording
        logger.info("cancel recording")
        os.remove(self.temp_wavfile)  # Delete the temporary audio file
        self.voice_mode_enabled = False
        self.cancel_button.setVisible(False)  # Hide cancel button
        self.voice_mode_button.setText("🎤")  # Reset the voice mode button
        self.voice_mode_button.setStyleSheet(RECORD_START_QSS)  # Reset record QSS
        self.input_field.setDisabled(False)
        self.input_field.setText("")

    def on_recording(self, elapsed: float):
        self.record_duration += elapsed
        self.input_field.setText(
            _t("ChatWidget.recording").format(dur=self.record_duration)
        )
        pass

    def add_message(
        self,
        text,
        *,
        is_sender=True,
        is_voice=False,
        is_voice_clickable=False,
        audio_file=None,
        voice_duration=None,
    ):
        bubble = MessageBubble(
            text, is_sender, is_voice, is_voice_clickable, audio_file, voice_duration
        )
        self.scroll_layout.addWidget(bubble)
        QApplication.processEvents()
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )

    def clear_messages(self):
        reply = QMessageBox.question(
            self,
            _t("ChatWidget.clear"),
            _t("ChatWidget.clear_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            for i in reversed(range(self.scroll_layout.count())):
                widget = self.scroll_layout.itemAt(i).widget()
                if widget:
                    widget.deleteLater()

    def send_message(self, audio=None):
        text = self.input_field.text().strip()

        if audio:  # priority: audio > text
            self.add_message(
                "语音消息示例1",
                is_sender=True,
                is_voice=True,
                is_voice_clickable=True,
                audio_file=audio,
                voice_duration=self.record_duration,
            )
        elif text:
            self.add_message(text, is_sender=True)
            self.input_field.clear()

        self.update_bubble_size()

    def update_bubble_size(self):
        for i in range(self.scroll_layout.count()):
            item = self.scroll_layout.itemAt(i).widget()
            if isinstance(item, MessageBubble):
                item.msg.setFixedWidth(item.get_dynamic_width(self.width()))

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.input_field.hasFocus() and self.input_field.text().strip():
                self.send_message()
            else:
                event.ignore()  # Let the event propagate if needed
        else:
            # Pass any other key events to the parent class
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        self.update_bubble_size()
        # Re-position the settings button when the window is resized
        self.settings_button.move(self.width() - 60, 10)
        super().resizeEvent(event)

    def closeEvent(self, event):
        # This method is called when the window is closed
        self.on_exit()  # Call the custom exit function
        event.accept()  # Accept the close event

    def on_exit(self):
        logger.info("Cleanup actions on exit...")
        # Place any cleanup code or final actions here
        for file_path in self.audio_files:
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    chat_widget = ChatWidget()
    chat_widget.setStyleSheet("background-color: #E9F5EA;")
    chat_widget.add_message(
        "你好！这是recv者的回复，消息可能会比较长，以测试换行功能是否正常工作。当窗口大小变化时，消息气泡应该会自动调整其宽度，确保用户体验。",
        is_sender=False,
    )
    chat_widget.add_message(
        "你好！这是发送者的回复，消息可能会比较长，以测试换行功能是否正常工作。当窗口大小变化时，消息气泡应该会自动调整其宽度，确保用户体验。",
        is_sender=True,
    )
    chat_widget.add_message("明白了，谢谢！", is_sender=False)
    chat_widget.add_message(
        "语音消息示例1",
        is_sender=True,
        is_voice=True,
        is_voice_clickable=False,
        voice_duration=12,
    )
    chat_widget.add_message("语音消息示例2", is_sender=False, is_voice=True, voice_duration=3)

    chat_widget.show()

    sys.exit(app.exec())
