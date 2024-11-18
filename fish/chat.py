import asyncio
import json
import os
import signal
import sys
import tempfile

from PyQt6.QtCore import QObject, Qt, QThreadPool, QTime, QUrl, pyqtSignal
from PyQt6.QtGui import QFont, QFontMetrics
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fish.config import config, save_config
from fish.modules.worker import (
    AsyncTaskRunner,
    AsyncTaskWorker,
    AudioPlayWorker,
    AudioRecordWorker,
    logger,
)
from fish.services.agent import (
    ChatState,
    FishE2EAgent,
    FishE2EEventType,
    ServeTextPart,
    ServeVQPart,
)
from fish.utils.audio import wav_chunk_header
from fish.utils.i18n import _t


class SettingsDialog(QDialog):
    def __init__(
        self,
        current_decoder_url: str = None,
        current_llm_url: str = None,
        current_proxy_url: str = None,
        current_ws_server_uri: str = None,
        current_system_prompt: str = None,
        current_system_audios: list = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(_t("SettingsDialog.title"))
        self.setModal(True)
        self.setMinimumSize(400, 200)

        # Set the current API URL and System Prompt if passed
        self.decoder_url = current_decoder_url or ""
        self.llm_url = current_llm_url or ""
        self.proxy_url = current_proxy_url or ""
        self.ws_server_uri = current_ws_server_uri or ""
        self.system_prompt = current_system_prompt or ""
        self.system_audios = current_system_audios or []

        layout = QVBoxLayout()

        # Create a form layout for the input fields
        form_layout = QFormLayout()

        # API URL input
        self.vqgan_api_input = QLineEdit(self.decoder_url)
        form_layout.addRow(_t("SettingsDialog.decoder_url"), self.vqgan_api_input)
        self.llm_api_input = QLineEdit(self.llm_url)
        form_layout.addRow(_t("SettingsDialog.llm_url"), self.llm_api_input)
        self.proxy_url_input = QLineEdit(self.proxy_url)
        form_layout.addRow(_t("SettingsDialog.proxy_url"), self.proxy_url_input)
        self.ws_server_uri_input = QLineEdit(self.ws_server_uri)
        self.ws_server_uri_input.setPlaceholderText(
            "Make it empty to disable websocket"
        )
        form_layout.addRow(_t("SettingsDialog.ws_server_uri"), self.ws_server_uri_input)
        layout.addLayout(form_layout)

        # System Prompt input
        layout.addWidget(QLabel(_t("SettingsDialog.sys_prompt")))
        self.system_prompt_input = QTextEdit()
        self.system_prompt_input.setPlainText(self.system_prompt.strip())
        layout.addWidget(self.system_prompt_input)

        # System Audio input
        layout.addWidget(QLabel(_t("SettingsDialog.sys_audio")))
        upload_button = QPushButton(_t("reference.upload"))
        upload_button.clicked.connect(self.upload_files)
        remove_button = QPushButton(_t("reference.remove"))
        remove_button.clicked.connect(self.remove_files)

        button_layout = QHBoxLayout()
        button_layout.addWidget(upload_button)
        button_layout.addWidget(remove_button)
        layout.addLayout(button_layout)

        # System Audio List
        self.file_list_widget = QListWidget()
        self.file_list_widget.setMinimumHeight(100)
        self.file_list_widget.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        for audio in self.system_audios:
            self.file_list_widget.addItem(audio)
        layout.addWidget(self.file_list_widget)

        save_button = QPushButton(_t("SettingsDialog.save_btn"))
        cancel_button = QPushButton(_t("SettingsDialog.cancel_btn"))
        save_button.clicked.connect(self.save_settings)
        cancel_button.clicked.connect(self.reject)

        button_layout = QHBoxLayout()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def upload_files(self):
        audios, _ = QFileDialog.getOpenFileNames(
            self, "Select Audio(s)", "", "Audio (*.wav *.flac *.mp3)"
        )
        if audios:
            self.file_list_widget.clear()
            self.system_audios.clear()
            for audio in audios:
                self.file_list_widget.addItem(audio)
                self.system_audios.append(audio)
            QMessageBox.information(
                self, "Upload Complete", f"Uploaded {len(audios)} audio(s)."
            )
        else:
            QMessageBox.warning(
                self, "No audio Selected", "Please select at least one file."
            )

    def remove_files(self):
        self.system_audios.clear()
        self.file_list_widget.clear()
        QMessageBox.warning(self, "Caution", "Successfully Removed ref audios.")

    def save_settings(self):
        # Save the API URL and System Prompt entered by the user
        self.decoder_url = self.vqgan_api_input.text().strip()
        self.llm_url = self.llm_api_input.text().strip()
        self.proxy_url = self.proxy_url_input.text().strip()
        self.ws_server_uri = self.ws_server_uri_input.text().strip()
        self.system_prompt = self.system_prompt_input.toPlainText().strip()

        if (
            self.llm_url and self.decoder_url and self.system_prompt
        ):  # Ensure both fields are not empty
            self.accept()
        else:
            QMessageBox.warning(
                self, "Invalid", "Input non-empty valid API URL and System Prompt"
            )


class ChatHistoryDialog(QDialog):
    def __init__(self, parent=None, chat_history: list[dict[str, str]] = None):
        super().__init__(parent)
        self.setWindowTitle("Chat History")
        self.setMinimumSize(400, 300)

        # Default chat history if none is provided
        self.chat_history = chat_history or [
            {"role": "system", "content": "(None, please refresh the history)"},
        ]

        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # Create QListWidget to display chat history
        self.history_list = QListWidget(self)
        self.history_list.setWordWrap(True)
        self.history_list.setStyleSheet("background-color: #f4f4f4;")

        # Populate the QListWidget with the chat history
        for item in self.chat_history:
            item = QListWidgetItem(
                "{k}: {v}".format(k=item.get("role"), v=item.get("content"))
            )
            self.history_list.addItem(item)

        # Add the history list to the layout
        layout.addWidget(self.history_list)

        # Add export button
        self.export_button = QPushButton("Export to JSON", self)
        self.export_button.clicked.connect(self.export_chat_history)
        layout.addWidget(self.export_button)

        # Set the dialog layout
        self.setLayout(layout)

    def export_chat_history(self):
        # Open a file dialog to select the export path
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        file_dialog.setNameFilter("JSON Files (*.json)")
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)

        if file_dialog.exec():
            file_path = file_dialog.selectedFiles()[0]

            if not file_path.endswith(".json"):
                file_path += ".json"  # Ensure the file ends with .json extension

            # Save the chat history to the selected file path
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(self.chat_history, f, ensure_ascii=False, indent=4)
                print(f"Chat history exported successfully to {file_path}")
            except Exception as e:
                print(f"Error exporting chat history: {e}")


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

    def get_current_text(self):
        return self.msg.text()

    def update_text(self, new_text: str):
        if not self.is_voice:
            self.text = new_text
            self.msg.setText(new_text)

    def update_duration(self, duration: float):
        if self.is_voice:
            self.voice_duration = duration
            self.msg.setText(f"🔊 {self.voice_duration:.1f}s")

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
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background-color: {"#C6E5F7" if self.is_sender else "#F1F1F1"};
                    border: 2px solid #E0E0E0;
                    font-size: 14px;
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
        text_width = font_metrics.horizontalAdvance(self.msg.text()) + 30
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

        self.decoder_url = config.decoder_url
        self.llm_url = config.llm_url
        self.proxy_url = config.proxy_url
        self.ws_server_uri = config.ws_server_uri
        self.system_prompt = config.system_prompt
        self.system_audios = []
        self.state = ChatState()
        self.thread_pool = QThreadPool.globalInstance()
        self.event_loop_message = asyncio.new_event_loop()
        self.event_loop_record = asyncio.new_event_loop()
        self.record_duration = 0.0
        self.async_msg_task = None
        self.initUI()
        self.init_messages()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(
            2
        )  # Main layout spacing, contains scroller and input widgets

        self.top_blank_area = QWidget()
        self.top_blank_area.setFixedHeight(50)
        main_layout.addWidget(self.top_blank_area)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("border: none;")
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_layout.setSpacing(0)
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
        self.send_button.clicked.connect(self.send_message_text)
        self.send_button.setStyleSheet(SEND_BUTTON_QSS)

        self.clear_button = QPushButton(_t("ChatWidget.clear_btn"))
        self.clear_button.clicked.connect(self.clear_messages)
        self.clear_button.setStyleSheet(CLEAN_QSS)

        self.stop_button = QPushButton(_t("ChatWidget.stop_btn"))
        self.stop_button.clicked.connect(self.stop_message_task)
        self.stop_button.setStyleSheet(CLEAN_QSS)

        input_layout.addWidget(self.voice_mode_button)
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_button)
        input_layout.addWidget(self.clear_button)
        input_layout.addWidget(self.stop_button)
        main_layout.addLayout(input_layout)

        # Add the settings button as an overlay in the top-right corner
        self.settings_button = QPushButton("⚙️")
        # self.settings_button.setStyleSheet("background: transparent; border: none;")
        self.settings_button.setFixedSize(32, 32)  # Adjust size as needed
        self.settings_button.clicked.connect(self.open_settings)
        # Position the settings button at the top-right corner as an overlay
        self.settings_button.setParent(self)
        self.settings_button.move(
            self.width() // 2 - 40, 10
        )  # Position with padding from the edge

        # Add the history button next to the settings button
        self.history_button = QPushButton(
            "📜"
        )  # A scroll icon or text to represent history
        self.history_button.setFixedSize(32, 32)
        self.history_button.clicked.connect(self.open_chat_history)
        self.history_button.setParent(self)
        self.history_button.move(
            self.width() // 2, 10
        )  # Positioned to the left of settings button

    def open_settings(self):
        # Open the settings dialog
        settings_dialog = SettingsDialog(
            self.decoder_url,
            self.llm_url,
            self.proxy_url,
            self.ws_server_uri,
            self.system_prompt,
            self.system_audios,
            self,
        )
        if settings_dialog.exec() == QDialog.DialogCode.Accepted:
            # Update the stored API URL after the dialog is closed
            config.llm_url = self.llm_url = settings_dialog.llm_url
            config.decoder_url = self.decoder_url = settings_dialog.decoder_url
            config.system_prompt = self.system_prompt = settings_dialog.system_prompt
            config.proxy_url = self.proxy_url = settings_dialog.proxy_url
            config.ws_server_uri = self.ws_server_uri = settings_dialog.ws_server_uri
            self.system_audios = settings_dialog.system_audios
            save_config()
            # Close the dialog on save
            QMessageBox.information(
                self,
                "Done",
                f"Configuration Saved!",
            )

    def open_chat_history(self):
        history = self.state.get_history()
        self.history_dialog = ChatHistoryDialog(self, history)
        self.history_dialog.exec()

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

        audio_recorder = AudioRecordWorker(
            loop=self.event_loop_record,
            save_as_file=True,
            output_file=self.temp_wavfile,
            ws_server_uri=self.ws_server_uri,
        )
        audio_recorder.audio_data_signal.connect(self.on_recording)

        self.async_record_runner = AsyncTaskRunner(audio_recorder)
        self.thread_pool.start(self.async_record_runner)
        logger.info("start recording")

        self.input_field.setDisabled(True)
        self.record_duration = 0.0
        self.input_field.setText(_t("ChatWidget.recording").format(dur=0))
        self.cancel_button.setVisible(True)  # Show the cancel button

    def stop_recording(self):
        if self.async_record_runner:
            self.async_record_runner.cancel()
            self.async_record_runner = None
        logger.info("stop recording")
        self.audio_files.append(self.temp_wavfile)
        self.start_message_task(audio=self.temp_wavfile)
        self.input_field.setDisabled(False)
        self.input_field.setText("")
        self.cancel_button.setVisible(False)  # Hide cancel button

    def cancel_recording(self):
        if self.async_record_runner:
            self.async_record_runner.cancel()
            self.async_record_runner = None
        logger.info("cancel recording")
        # os.remove(self.temp_wavfile)  # Delete the temporary audio file
        self.audio_files.append(self.temp_wavfile)
        self.voice_mode_enabled = False
        self.cancel_button.setVisible(False)  # Hide cancel button
        self.voice_mode_button.setText("🎤")  # Reset the voice mode button
        self.voice_mode_button.setStyleSheet(RECORD_START_QSS)  # Reset record QSS
        self.input_field.setDisabled(False)
        self.input_field.setText("")

    def on_recording(self, elapsed: float):
        self.record_duration = elapsed
        self.input_field.setText(
            _t("ChatWidget.recording").format(dur=self.record_duration)
        )
        pass

    def init_messages(self):
        if self.state.added_systext is False and self.system_prompt:
            self.state.added_systext = True
            self.state.append_to_chat_ctx(
                ServeTextPart(text=self.system_prompt), role="system"
            )

    def add_message(
        self,
        text,
        *,
        is_sender=True,
        is_voice=False,
        is_voice_clickable=False,
        audio_file=None,
        voice_duration=None,
    ) -> MessageBubble:
        bubble = MessageBubble(
            text, is_sender, is_voice, is_voice_clickable, audio_file, voice_duration
        )
        self.scroll_layout.addWidget(bubble)
        QApplication.processEvents()

        return bubble

    def clear_messages(self):
        reply = QMessageBox.question(
            self,
            _t("ChatWidget.clear"),
            _t("ChatWidget.clear_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.state.clear()
            for i in reversed(range(self.scroll_layout.count())):
                widget = self.scroll_layout.itemAt(i).widget()
                if widget:
                    widget.deleteLater()
            self.init_messages()

    def send_message_text(self):
        text = self.input_field.text().strip()
        if text:
            self.input_field.clear()
            self.start_message_task(text=text)

    def start_message_task(self, *, text: str = None, audio: str = None):
        message_worker = MessageWorker(
            input_text=text,
            input_audio=audio,
            state=self.state,
            llm_url=self.llm_url,
            decoder_url=self.decoder_url,
            system_prompt=self.system_prompt,
            system_audios=self.system_audios,
            loop=self.event_loop_message,
        )

        message_worker.finished.connect(self.on_message_task_finished)
        message_worker.add_message_signal.connect(self.on_add_message)
        message_worker.update_bubble_signal.connect(self.on_update_bubble)
        message_worker.update_duration_signal.connect(self.on_update_duration)
        message_worker.update_text_signal.connect(self.on_update_text)
        # worker -> QRunnable -> QThreadPool
        self.async_msg_runner = AsyncTaskRunner(message_worker)
        logger.info("start async message runner")
        self.thread_pool.start(self.async_msg_runner)
        pass

    def stop_message_task(self):
        if self.async_msg_runner:
            self.async_msg_runner.cancel()
            self.async_msg_runner = None

    def on_message_task_finished(self, audio):
        self.audio_files.append(audio)
        logger.info("Message Task Complete")
        pass

    def on_add_message(self, text, is_sender, is_voice, audio, duration):
        self.add_message(
            text,
            is_sender=is_sender,
            is_voice=is_voice,
            is_voice_clickable=is_voice,
            audio_file=audio,
            voice_duration=self.record_duration if is_sender else duration,
        )

    def on_update_bubble(self, mode):
        self.update_bubble_size(mode)

    def on_update_duration(self, dur):
        num_bubbles = self.scroll_layout.count()
        assert num_bubbles >= 2
        item: MessageBubble = self.scroll_layout.itemAt(num_bubbles - 2).widget()
        item.update_duration(dur)

    def on_update_text(self, text):
        num_bubbles = self.scroll_layout.count()
        assert num_bubbles >= 1
        item: MessageBubble = self.scroll_layout.itemAt(num_bubbles - 1).widget()
        item.update_text(text)

    def update_bubble_size(self, mode: str = "all"):
        start_idx = self.scroll_layout.count() - 1 if mode == "last" else 0
        for i in range(start_idx, self.scroll_layout.count(), 1):
            item = self.scroll_layout.itemAt(i).widget()
            if isinstance(item, MessageBubble):
                item.msg.setFixedWidth(item.get_dynamic_width(self.width()))
        if mode == "last":
            # Drag scroll bar to the bottom
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().maximum()
            )
        pass

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.Modifier.CTRL and event.key() == Qt.Key.Key_B:
            self.stop_message_task()
            event.accept()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.input_field.hasFocus():
                self.send_message_text()
            else:
                event.ignore()  # Let the event propagate if needed
        else:
            # Pass any other key events to the parent class
            super().keyPressEvent(event)
        pass

    def resizeEvent(self, event):
        self.update_bubble_size()
        # Re-position the settings button when the window is resized
        self.settings_button.move(self.width() // 2 - 40, 10)
        self.history_button.move(self.width() // 2, 10)
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


class MessageWorker(AsyncTaskWorker):
    finished = pyqtSignal(str)  # tmp audio
    add_message_signal = pyqtSignal(
        str, bool, bool, str, float
    )  # text, is_sender, is_voice, audio, duration
    update_bubble_signal = pyqtSignal(str)
    update_duration_signal = pyqtSignal(float)
    update_text_signal = pyqtSignal(str)

    def __init__(
        self,
        input_text: str,
        input_audio: str,
        state: ChatState,
        llm_url: str,
        decoder_url: str,
        system_prompt: str,
        system_audios: list,
        loop: asyncio.AbstractEventLoop,
    ):
        super().__init__(loop)
        self.input_text = input_text
        self.input_audio = input_audio
        self.state = state
        self.agent = FishE2EAgent(llm_url, decoder_url)
        self.system_prompt = system_prompt
        self.system_audios = system_audios

    async def send_message_async(self, cancel_event: asyncio.Event):
        text = self.input_text
        audio = self.input_audio
        agent = self.agent

        # Step 1: Encode audio using VQGAN (text is previously encoded in init_messages)

        if self.state.added_sysaudio is False and len(self.system_audios) > 0:
            self.state.added_sysaudio = True
            sys_codes = await asyncio.gather(
                *[agent.get_codes(audio) for audio in self.system_audios]
            )

            for sys_code in sys_codes:
                self.state.append_to_chat_ctx(
                    ServeVQPart(codes=sys_code), role="system"
                )

        # Step 2: Prepare LLM request
        if audio:  # priority: audio > text
            user_code = await agent.get_codes(audio)
            self.state.append_to_chat_ctx(ServeVQPart(codes=user_code), role="user")
            self.add_message_signal.emit(
                "",
                True,
                True,
                audio,
                len(user_code[0]) / 21,
            )
        elif text:
            user_code = None
            self.state.append_to_chat_ctx(ServeTextPart(text=text), role="user")
            self.add_message_signal.emit(text, True, False, "", 0)

        else:
            raise Exception

        self.update_bubble_signal.emit("last")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_wavfile = temp_file.name

        self.add_message_signal.emit("", False, True, temp_wavfile, 0)
        self.update_bubble_signal.emit("last")
        self.add_message_signal.emit(
            "",
            False,
            False,
            "",
            0,
        )
        self.update_bubble_signal.emit("last")

        # Step 3: Generate audio and text segments in real-time
        async def wave_generator(audio_data: bytes, cancel_event: asyncio.Event):
            chunk_size = 32768  # 32KB = 16K samples = 16384 / 44100 = 0.372 s
            offset = 0

            while offset + chunk_size <= len(audio_data):
                # one method to stop async audioplayer is to cut off the wav-stream
                if cancel_event.is_set():
                    break
                yield audio_data[offset : offset + chunk_size]
                offset += chunk_size

            if cancel_event.is_set():
                yield b""
            elif offset < len(audio_data):
                yield audio_data[offset:]

        async def infostream_generator(cancel_event: asyncio.Event):
            total_seg_time = 0.0
            yield wav_chunk_header()  # Initial header

            try:
                async for event in agent.stream(
                    chat_ctx={"messages": self.state.conversation}
                ):
                    if cancel_event.is_set():
                        break

                    if event.type == FishE2EEventType.SPEECH_SEGMENT:
                        self.state.append_to_chat_ctx(ServeVQPart(codes=event.vq_codes))
                        total_seg_time += len(event.vq_codes[0]) / 21

                        audio_data = bytes(event.frame.data)
                        async for chunk in wave_generator(audio_data, cancel_event):
                            yield chunk

                        self.update_duration_signal.emit(total_seg_time)

                    elif event.type == FishE2EEventType.TEXT_SEGMENT:
                        self.state.append_to_chat_ctx(ServeTextPart(text=event.text))
                        self.update_text_signal.emit(
                            self.state.repr_message(self.state.conversation[-1])
                        )
                        self.update_bubble_signal.emit("last")

            except asyncio.CancelledError:
                logger.warning("Infostream generator was cancelled.")
                raise  # Re-raise to assure interruption

        # Step 4: Play audio (streaming)

        audio_player = AudioPlayWorker(audio_path=temp_wavfile, streaming=True)
        audio_player.set_chunks(infostream_generator(cancel_event))
        await audio_player.run_async()
        self.finished.emit(temp_wavfile)

    async def _execute_task(self):
        await self.send_message_async(self.cancel_event)


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
    chat_widget.add_message(
        "语音消息示例2", is_sender=False, is_voice=True, voice_duration=3
    )

    chat_widget.show()

    sys.exit(app.exec())
