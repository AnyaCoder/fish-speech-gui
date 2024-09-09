import os
import sys

import httpx
import ormsgpack

from fish.audio import ServeReferenceAudio, ServeTTSRequest, get_devices

import pkg_resources
import qdarktheme
import requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMutex, QWaitCondition, QUrl
from PyQt6.QtGui import QIcon
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtWidgets import (
    QListWidget,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from fish.config import application_path, config, load_config, save_config
from fish.i18n import _t, language_map

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowIcon(QIcon(str(application_path / "assets" / "icon.png")))

        version = pkg_resources.get_distribution("fish-speech-gui").version
        # remove +editable if it exists
        version = version.split("+")[0]
        self.setWindowTitle(_t("title").format(version=version))

        self.main_layout = QVBoxLayout()
        # Stick to the top
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.setup_ui_settings()
        self.setup_backend_settings()
        self.setup_device_settings()
        self.setup_audio_settings()
        self.setup_reference_settings()
        self.setup_textinput_settings()
        self.setup_audioplayer_settings()

        self.setup_action_buttons()
        self.setLayout(self.main_layout)

        # Use size hint to set a reasonable size
        self.setMinimumWidth(900)

        self.files = []

    def setup_ui_settings(self):
        # we have language and backend settings in the first row
        row = QHBoxLayout()
        row.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # set up a theme combo box
        row.addWidget(QLabel(_t("theme.name")))
        self.theme_combo = QComboBox()
        self.theme_combo.addItem(_t("theme.auto"), "auto")
        self.theme_combo.addItem(_t("theme.light"), "light")
        self.theme_combo.addItem(_t("theme.dark"), "dark")
        self.theme_combo.setCurrentText(_t(f"theme.{config.theme}"))
        self.theme_combo.currentIndexChanged.connect(self.change_theme)
        self.theme_combo.setMinimumWidth(100)
        row.addWidget(self.theme_combo)

        # set up language combo box
        row.addWidget(QLabel(_t("i18n.language")))
        self.language_combo = QComboBox()

        for k, v in language_map.items():
            self.language_combo.addItem(v, k)

        self.language_combo.setCurrentText(language_map.get(config.locale, 'en_US'))
        self.language_combo.currentIndexChanged.connect(self.change_language)
        self.language_combo.setMinimumWidth(150)
        row.addWidget(self.language_combo)

        # save button
        self.save_button = QPushButton(_t("config.save"))
        self.save_button.clicked.connect(self.save_config)
        row.addWidget(self.save_button)

        # load button
        self.load_button = QPushButton(_t("config.load"))
        self.load_button.clicked.connect(self.load_config)
        row.addWidget(self.load_button)

        self.main_layout.addLayout(row)

    def setup_device_settings(self):
        # second row: a group box for audio device settings
        row = QGroupBox(_t("audio_device.name"))
        row_layout = QGridLayout()
        row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # fetch devices
        input_devices, output_devices = get_devices()

        # input device
        row_layout.addWidget(QLabel(_t("audio_device.input")), 0, 0)
        self.input_device_combo = QComboBox()
        for device in input_devices:
            self.input_device_combo.addItem(device["name"], device["id"])

        # find the current device from config
        if config.input_device is not None:
            for i in range(self.input_device_combo.count()):
                if self.input_device_combo.itemData(i) == config.input_device:
                    self.input_device_combo.setCurrentIndex(i)
                    break
            else:
                # not found, use default
                self.input_device_combo.setCurrentIndex(0)
                config.input_device = self.input_device_combo.itemData(0)

        self.input_device_combo.setFixedWidth(300)
        row_layout.addWidget(self.input_device_combo, 0, 1)

        # output device
        row_layout.addWidget(QLabel(_t("audio_device.output")), 1, 0)
        self.output_device_combo = QComboBox()
        for device in output_devices:
            self.output_device_combo.addItem(device["name"], device["id"])

        # find the current device from config
        if config.output_device is not None:
            for i in range(self.output_device_combo.count()):
                if self.output_device_combo.itemData(i) == config.output_device:
                    self.output_device_combo.setCurrentIndex(i)
                    break
            else:
                # not found, use default
                self.output_device_combo.setCurrentIndex(0)
                config.output_device = self.output_device_combo.itemData(0)

        self.input_device_combo.setFixedWidth(300)
        row_layout.addWidget(self.output_device_combo, 1, 1)

        row.setLayout(row_layout)

        self.main_layout.addWidget(row)

    def setup_audio_settings(self):
        # third row: a group box for audio settings
        row = QGroupBox(_t("audio.name"))
        row_layout = QGridLayout()
        
        # db_threshold, pitch_shift
        row_layout.addWidget(QLabel(_t("audio.chunk_length")), 0, 0)
        self.chunk_length_slider = QSlider(Qt.Orientation.Horizontal)
        self.chunk_length_slider.setMinimum(100)
        self.chunk_length_slider.setMaximum(300)
        self.chunk_length_slider.setSingleStep(1)
        self.chunk_length_slider.setTickInterval(1)
        self.chunk_length_slider.setValue(config.chunk_length)
        row_layout.addWidget(self.chunk_length_slider, 0, 1)
        self.chunk_length_label = QLabel(f"{config.chunk_length}")
        self.chunk_length_label.setFixedWidth(50)
        row_layout.addWidget(self.chunk_length_label, 0, 2)
        self.chunk_length_slider.valueChanged.connect(
            lambda v: self.chunk_length_label.setText(f"{v}")
        )

        row_layout.addWidget(QLabel(_t("audio.max_new_tokens")), 0, 3)
        self.max_new_tokens_slider = QSlider(Qt.Orientation.Horizontal)
        self.max_new_tokens_slider.setMinimum(1024)
        self.max_new_tokens_slider.setMaximum(4096)
        self.max_new_tokens_slider.setSingleStep(128)
        self.max_new_tokens_slider.setTickInterval(128)
        self.max_new_tokens_slider.setValue(config.max_new_tokens)
        row_layout.addWidget(self.max_new_tokens_slider, 0, 4)
        self.max_new_tokens_label = QLabel(f"{config.max_new_tokens}")
        self.max_new_tokens_label.setFixedWidth(50)
        row_layout.addWidget(self.max_new_tokens_label, 0, 5)
        self.max_new_tokens_slider.valueChanged.connect(
            lambda v: self.max_new_tokens_label.setText(f"{v}")
        )

        # performance related
        # top_p, fade_duration
        row_layout.addWidget(QLabel(_t("audio.top_p")), 1, 0)
        self.top_p_slider = QSlider(Qt.Orientation.Horizontal)
        self.top_p_slider.setMinimum(100)
        self.top_p_slider.setMaximum(1000)
        self.top_p_slider.setSingleStep(100)
        self.top_p_slider.setTickInterval(100)
        self.top_p_slider.setValue(config.top_p)
        row_layout.addWidget(self.top_p_slider, 1, 1)
        self.top_p_label = QLabel(f"{config.top_p / 1000:.1f}")
        self.top_p_label.setFixedWidth(50)
        row_layout.addWidget(self.top_p_label, 1, 2)
        self.top_p_slider.valueChanged.connect(
            lambda v: self.top_p_label.setText(f"{v / 1000:.1f}")
        )

        row_layout.addWidget(QLabel(_t("audio.repetition_penalty")), 1, 3)
        self.repetition_penalty_slider = QSlider(Qt.Orientation.Horizontal)
        self.repetition_penalty_slider.setMinimum(900)
        self.repetition_penalty_slider.setMaximum(2000)
        self.repetition_penalty_slider.setSingleStep(10)
        self.repetition_penalty_slider.setTickInterval(10)
        self.repetition_penalty_slider.setValue(config.repetition_penalty)
        row_layout.addWidget(self.repetition_penalty_slider, 1, 4)
        self.repetition_penalty_label = QLabel(f"{config.repetition_penalty / 1000:.2f}")
        self.repetition_penalty_label.setFixedWidth(50)
        row_layout.addWidget(self.repetition_penalty_label, 1, 5)
        self.repetition_penalty_slider.valueChanged.connect(
            lambda v: self.repetition_penalty_label.setText(f"{v / 1000:.2f}")
        )

        # Extra duration, input denoise, output denoise in next row
        row_layout.addWidget(QLabel(_t("audio.temperature")), 2, 0)
        self.temperature_slider = QSlider(Qt.Orientation.Horizontal)
        self.temperature_slider.setMinimum(50)
        self.temperature_slider.setMaximum(1000)
        self.temperature_slider.setSingleStep(10)
        self.temperature_slider.setTickInterval(10)
        self.temperature_slider.setValue(config.temperature)
        row_layout.addWidget(self.temperature_slider, 2, 1)
        self.temperature_label = QLabel(f"{config.temperature / 1000:.2f}")
        self.temperature_label.setFixedWidth(50)
        row_layout.addWidget(self.temperature_label, 2, 2)
        self.temperature_slider.valueChanged.connect(
            lambda v: self.temperature_label.setText(f"{v / 1000:.2f}")
        )

        row_layout.addWidget(QLabel(_t("audio.mp3_bitrate")), 2, 3)
        self.mp3_bitrate_combo = QComboBox()
        self.mp3_bitrate_combo.addItems(["64", "128", "192"])
        self.mp3_bitrate_combo.setFixedWidth(100)
        if config.mp3_bitrate is not None:
            for i in range(self.mp3_bitrate_combo.count()):
                if self.mp3_bitrate_combo.itemData(i) == config.mp3_bitrate:
                    self.mp3_bitrate_combo.setCurrentIndex(i)
                    break
            else:
                # not found, use default
                self.mp3_bitrate_combo.setCurrentIndex(0)
                config.mp3_bitrate = self.mp3_bitrate_combo.itemData(0)

        row_layout.addWidget(self.mp3_bitrate_combo, 2, 4)
    
        row.setLayout(row_layout)
        self.main_layout.addWidget(row)
    
    def setup_reference_settings(self):
        row = QGroupBox()
        row.setTitle(_t("reference.name"))
        row_layout = QGridLayout()

        # set up reference_id input, and a test button
        self.ref_id_label = QLabel(_t("reference.id"))
        self.ref_id_label.setFixedWidth(100)
        row_layout.addWidget(self.ref_id_label, 0, 0, 1, 1)
        self.ref_id_input = QLineEdit()
        self.ref_id_input.setPlaceholderText(_t("reference.stmt"))
        self.ref_id_input.setText(config.ref_id)
        row_layout.addWidget(self.ref_id_input, 0, 1, 1, 2)

        self.file_list_widget = QListWidget()
        # self.file_list_widget.setFixedWidth(300)
        self.file_list_widget.setMinimumHeight(50)
        self.file_list_widget.setMaximumHeight(100)
        self.file_list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded) 
        row_layout.addWidget(self.file_list_widget, 1, 0, 3, 2)
        
        row_layout.addWidget(QLabel(_t("reference.upload_info")), 1, 2, 1, 1)

        self.upload_button = QPushButton(_t("reference.upload"))
        self.upload_button.clicked.connect(self.upload_files)
        self.upload_button.setFixedWidth(100)
        row_layout.addWidget(self.upload_button, 2, 2, 1, 1)

        self.upload_button = QPushButton(_t("reference.remove"))
        self.upload_button.clicked.connect(self.remove_files)
        self.upload_button.setFixedWidth(100)
        row_layout.addWidget(self.upload_button, 3, 2, 1, 1)

        row.setLayout(row_layout)
        self.main_layout.addWidget(row)

    def setup_textinput_settings(self):
        row = QGroupBox()
        row.setTitle(_t("tts_input.name"))
        row.setFixedHeight(150)
        row_layout = QGridLayout()
        self.text_edit = QTextEdit()

        self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)  
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded) 
        row_layout.addWidget(self.text_edit, 0, 0)

        row.setLayout(row_layout)
        self.main_layout.addWidget(row)

    def setup_audioplayer_settings(self):

        row = QGroupBox()
        row.setTitle(_t("tts_output.name"))
        row_layout = QGridLayout()

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 100)
        self.progress_slider.sliderMoved.connect(self.set_position)
        row_layout.addWidget(self.progress_slider, 0, 0, 1, 6)

        self.time_label = QLabel("00:00 / 00:00")
        row_layout.addWidget(self.time_label, 0, 6, 1, 2, Qt.AlignmentFlag.AlignCenter)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(config.volume)
        self.volume_slider.sliderMoved.connect(self.set_volume)
        row_layout.addWidget(QLabel("Volume ↕"), 1, 0, 1, 1, Qt.AlignmentFlag.AlignCenter)
        row_layout.addWidget(self.volume_slider, 1, 1, 1, 4)
        self.volume_label = QLabel(f"{config.volume}")
        self.volume_slider.valueChanged.connect(
            lambda v: self.volume_label.setText(f"{v}")
        )
        row_layout.addWidget(self.volume_label, 1, 5, 1, 1, Qt.AlignmentFlag.AlignCenter)
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.toggle_play)
        row_layout.addWidget(self.play_button, 1, 6, 1, 2)


        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(50, 200)  # 50% 到 200% 的播放速率
        self.speed_slider.setValue(100)  # 初始速率为 100%
        self.speed_slider.sliderMoved.connect(self.set_speed)
        row_layout.addWidget(QLabel("Speed >>"), 2, 0, 1, 1, Qt.AlignmentFlag.AlignCenter)
        row_layout.addWidget(self.speed_slider, 2, 1, 1, 4)
        self.speed_label = QLabel(f"{config.speed / 100:.2f} x")
        self.speed_slider.valueChanged.connect(
            lambda v: self.speed_label.setText(f"{v / 100:.2f} x")
        )
        row_layout.addWidget(self.speed_label, 2, 5, 1, 1, Qt.AlignmentFlag.AlignCenter)
        self.open_button = QPushButton("Open Audio File")
        self.open_button.clicked.connect(self.open_file)
        row_layout.addWidget(self.open_button, 2, 6, 1, 2)

        row.setLayout(row_layout)

        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)
        self.main_layout.addWidget(row)

    def setup_backend_settings(self):
        widget = QGroupBox()
        widget.setTitle(_t("backend.title"))
        row = QHBoxLayout()

        # protocol
        row.addWidget(QLabel(_t("backend.protocol_label")))
        self.backend_protocol = QComboBox()
        self.backend_protocol.setMinimumWidth(75)
        self.backend_protocol.addItems(["v1"])
        self.backend_protocol.setCurrentText("v1")
        row.addWidget(self.backend_protocol)

        # set up backend (url) input, and a test button
        row.addWidget(QLabel(_t("backend.name")))
        self.backend_input = QLineEdit()
        self.backend_input.setText(config.backend)
        row.addWidget(self.backend_input)

        self.test_button = QPushButton(_t("backend.test"))
        self.test_button.clicked.connect(self.test_backend)
        row.addWidget(self.test_button)

        widget.setLayout(row)
        self.main_layout.addWidget(widget)


    def setup_action_buttons(self):
        row = QWidget()
        row_layout = QHBoxLayout()
        row_layout.addStretch(1)

        self.start_button = QPushButton(_t("action.start"))
        self.start_button.clicked.connect(self.start_conversion)
        row_layout.addWidget(self.start_button)

        self.stop_button = QPushButton(_t("action.stop"))
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_conversion)
        row_layout.addWidget(self.stop_button)

        self.latency_label = QLabel(_t("action.latency").format(latency=0))
        row_layout.addWidget(self.latency_label)

        row.setLayout(row_layout)
        self.main_layout.addWidget(row)

    def change_theme(self, index):
        config.theme = self.theme_combo.itemData(index)

        save_config()
        qdarktheme.setup_theme(config.theme)

    def change_language(self, index):
        config.locale = self.language_combo.itemData(index)
        save_config()

        # pop up a message box to tell user app will restart
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setText(_t("i18n.restart_msg"))
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        ret = msg_box.exec()

        if ret == QMessageBox.StandardButton.Yes:
            if len(sys.argv) == 1:
                sys.argv.insert(0, sys.executable)
            print(sys.argv)
            os.execv(sys.argv[0], sys.argv)

    def upload_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", "Audio / Text (*.wav *.lab *.flac *.mp3)")
        if files:
            self.files = files
            self.file_list_widget.clear()
            for file in files:
                self.file_list_widget.addItem(file)
            QMessageBox.information(self, "Upload Complete", f"Uploaded {len(files)} files.")
        else:
            QMessageBox.warning(self, "No Files Selected", "Please select at least one file.")

    def remove_files(self):
        self.files = []
        self.file_list_widget.clear()
        QMessageBox.warning(self, "Caution", "Successfully Removed References.")


    def test_backend(self):
        backend = self.backend_input.text()

        try:
            response = requests.options(backend, timeout=5)
        except:
            response = None

        message_box = QMessageBox()

        if response is not None and response.status_code == 200:
            message_box.setIcon(QMessageBox.Icon.Information)
            message_box.setText(_t("backend.test_succeed"))
            config.backend = backend
            save_config()
        else:
            message_box.setIcon(QMessageBox.Icon.Question)
            message_box.setText(_t("backend.test_failed"))

        message_box.exec()

    def save_config(self, save_to_file=True):
        config.backend = self.backend_input.text()
        config.input_device = self.input_device_combo.currentData()
        config.output_device = self.output_device_combo.currentData()
        config.chunk_length = self.chunk_length_slider.value()
        config.max_new_tokens = self.max_new_tokens_slider.value()
        config.repetition_penalty = self.repetition_penalty_slider.value()
        config.repetition_penalty = self.repetition_penalty_slider.value()
        config.temperature = self.temperature_slider.value()
        config.mp3_bitrate = self.mp3_bitrate_combo.currentData()

        save_config()

        # pop up a message box to tell user if they want to save the config to a file
        if not save_to_file:
            return

        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setText(_t("config.save_msg"))
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)

        ret = msg_box.exec()
        if ret == QMessageBox.StandardButton.No:
            return

        file_name, _ = QFileDialog.getSaveFileName(
            self, _t("config.save_title"), "", "YAML (*.yaml)"
        )

        if not file_name:
            return

        save_config(file_name)

    def load_config(self):
        # pop up a message box to select a config file
        file_name, _ = QFileDialog.getOpenFileName(
            self, _t("config.load_title"), "", "YAML (*.yaml)"
        )

        if not file_name:
            return

        load_config(file_name)
        save_config()

        # pop up a message box to tell user app will restart
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setText(_t("config.load_msg"))
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()

        os.execv(sys.argv[0], sys.argv)

    def open_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Audio File", "", "Audio Files (*.mp3 *.wav *.flac)")
        if file_name:
            self.player.setSource(QUrl.fromLocalFile(file_name))
            self.play_button.setText("Play")

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_button.setText("Play")
        else:
            self.player.play()
            self.play_button.setText("Pause")

    def set_position(self, position):
        self.player.setPosition(position)

    def set_speed(self, speed):
        playback_rate = speed / 100.0 
        self.player.setPlaybackRate(playback_rate)

    def set_volume(self, volume):
        self.audio_output.setVolume(volume / 100)

    def update_position(self, position):
        self.progress_slider.setValue(position)
        self.update_time_label()

    def update_duration(self, duration):
        self.progress_slider.setRange(0, duration)
        self.update_time_label()

    def update_time_label(self):
        current_time = self.format_time(self.player.position())
        total_time = self.format_time(self.player.duration())
        self.time_label.setText(f"{current_time} / {total_time}")

    @staticmethod
    def format_time(ms):
        seconds = (ms // 1000) % 60
        minutes = (ms // (1000 * 60)) % 60
        return f"{minutes:02}:{seconds:02}"

    def start_conversion(self):
        self.save_config(save_to_file=False)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        self.tts_worker = TTSWorker()
        self.tts_worker.finished.connect(self.on_conversion_finished)
        self.tts_worker.start()

    def stop_conversion(self):
        self.tts_worker.stop()  
        self.tts_worker.wait()  
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def on_conversion_finished(self):
        self.stop_conversion()


class TTSWorker(QThread):
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.mutex = QMutex()
        self.wait_condition = QWaitCondition() 
        self._stop_requested = False 

    def run(self):

        request = ServeTTSRequest(
            text="你说的对, 但是原神是一款由米哈游自主研发的开放世界手游.",
            references=[
                ServeReferenceAudio(
                    audio=open("lengyue.wav", "rb").read(),
                    text=open("lengyue.lab", "r", encoding="utf-8").read(),
                )
            ],
            streaming=True,
        )

        with (
            httpx.Client() as client,
            open("hello.wav", "wb") as f,
        ):
            with client.stream(
                "POST",
                "http://127.0.0.1:8080/v1/tts",
                content=ormsgpack.packb(request, option=ormsgpack.OPT_SERIALIZE_PYDANTIC),
                headers={
                    "authorization": "Bearer YOUR_API_KEY",
                    "content-type": "application/msgpack",
                },
                timeout=None,
            ) as response:
                for chunk in response.iter_bytes():

                    self.mutex.lock()
                    if self._stop_requested:
                        print("TTS is interrupted!")
                        self.mutex.unlock()
                        break
                    self.mutex.unlock()
                    f.write(chunk)

        self.finished.emit() 

    def stop(self):
        self.mutex.lock()
        self._stop_requested = True
        self.mutex.unlock()
        self.wait_condition.wakeAll()