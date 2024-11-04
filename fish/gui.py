import datetime
import os
import subprocess
import sys

import pkg_resources
import qdarktheme
import requests
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from fish.config import application_path, config, load_config, save_config
from fish.fap import (
    FAPFrequencyStatWidget,
    FAPLengthStatWidget,
    FAPLoudNormWidget,
    FAPMergeLabWidget,
    FAPResampleWidget,
    FAPSeparateWidget,
    FAPSliceAudioWidget,
    FAPToWavWidget,
    FAPTranscribeWidget,
)
from fish.input import TextEditorWidget
from fish.modules.console import ConsoleStream, ConsoleWidget
from fish.modules.globals import STOP_BUTTON_QSS
from fish.modules.registry import widget_registry
from fish.modules.worker import TTSWorker
from fish.utils.audio import get_devices
from fish.utils.file import *
from fish.utils.i18n import _t, language_map


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowIcon(QIcon(str(application_path / "assets" / "icon.png")))
        self.setGeometry(100, 100, 800, 600)
        version = pkg_resources.get_distribution("fish-speech-gui").version
        # remove +editable if it exists
        version = version.split("+")[0]
        self.setWindowTitle(_t("title").format(version=version))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        widget_registry.register(central_widget, "central_widget")
        self.setup_background_image(central_widget)

        # Console
        self.console_widget = ConsoleWidget(max_lines=1000)
        self.python = QLineEdit()

        self.main_layout = QVBoxLayout(central_widget)

        self.tab_widget = QTabWidget()
        widget_registry.register(self.tab_widget, "tab_widget")
        self.main_layout.addWidget(self.tab_widget)

        self.tab_widget.setStyleSheet(
            """                      
            QTabWidget {
                background: transparent;
                border: 2px solid #0FA891D2;
                border-radius: 10px;
            }
            QTabWidget > QStackedWidget {
                background-color: rgba(255, 255, 255, 0.5);
                border: 1px solid #FCAAAA8F;
                border-radius: 10px;
            }
        """
        )
        self.tab_widget.addTab(self.create_settings_tab1(), _t("tab.page1"))
        self.tab_widget.addTab(self.create_settings_tab2(), _t("tab.page2"))
        self.tab_widget.addTab(self.create_settings_tab3(), _t("tab.page3"))
        self.tab_widget.addTab(self.create_settings_tab4(), _t("tab.page4"))
        self.tab_widget.addTab(self.create_settings_tab5(), _t("tab.page5"))
        self.tab_widget.addTab(self.create_settings_tab6(), _t("tab.page6"))

        # Stick to the top

        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setup_action_buttons(self.main_layout)

        self.change_theme(self.theme_combo.currentIndex())  # initialize theme for 1st

        # Use size hint to set a reasonable size
        self.setMinimumWidth(800)

        # Redefined Stream
        self.stdout_stream = ConsoleStream()
        self.stderr_stream = ConsoleStream()
        self.stdout_stream.new_message.connect(
            lambda msg: self.update_console(msg, "white")
        )
        self.stderr_stream.new_message.connect(
            lambda msg: self.update_console(msg, "red")
        )
        sys.stdout = self.stdout_stream
        sys.stderr = self.stderr_stream

        # Uploaded ref files
        self.files = []

    def set_widget_background(
        self,
        widget: QWidget,
        *,
        alpha: int = 100,
        r: int = 255,
        g: int = 255,
        b: int = 255,
        border_radius: int = 10,
        pane_extra: str = "",
        widget_extra: str = "",
    ):
        widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        widget.setStyleSheet(
            f"""
            QTabWidget::pane {{
                background-color: rgba({r}, {g}, {b}, {alpha});
                {pane_extra}
                border-radius: {border_radius}px;
            }}
            QFrame, QWidget#{widget.objectName()} {{
                background-color: rgba({r}, {g}, {b}, {alpha});
                {widget_extra}
                border-radius: {border_radius}px;
            }}
        """
        )

    def setup_background_image(self, widget: QWidget):
        background_path = str(application_path / "assets" / "bg.png")

        background_label = QLabel(widget)
        background_pixmap = QPixmap(background_path)

        if background_pixmap.isNull():
            print("Failed to load background image")
            return

        background_label.setPixmap(background_pixmap)
        background_label.setScaledContents(True)
        background_label.resize(widget.size())
        background_label.lower()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        widget.installEventFilter(self)
        self.background_label = background_label

    def eventFilter(self, source, event):
        if event.type() == event.Type.Resize and source == self.centralWidget():
            self.background_label.resize(source.size())
        return super().eventFilter(source, event)

    def update_console(self, msg, color):
        self.console_widget.update_console(msg, color)

    def create_settings_tab1(self):
        tab1 = QWidget()
        layout1 = QVBoxLayout()
        widget_registry.register(tab1, "tab1")

        self.setup_ui_settings(layout1)
        self.setup_backend_settings(layout1)
        self.setup_device_settings(layout1)
        self.setup_audio_settings(layout1)
        self.setup_reference_settings(layout1)

        tab1.setLayout(layout1)
        return tab1

    def create_settings_tab2(self):
        tab2 = QWidget()
        layout2 = QVBoxLayout()
        widget_registry.register(tab2, "tab2")
        self.setup_textinput_settings(layout2)
        self.setup_audioplayer_settings(layout2)

        tab2.setLayout(layout2)
        return tab2

    def create_settings_tab3(self):
        tab3 = QWidget()
        layout3 = QVBoxLayout()
        widget_registry.register(tab3, "tab3")
        self.fap_towav_widget = FAPToWavWidget(self.console_widget, self.python)
        self.fap_resample_widget = FAPResampleWidget(self.console_widget, self.python)
        self.fap_loudnorm_widget = FAPLoudNormWidget(self.console_widget, self.python)

        layout3.addWidget(self.fap_towav_widget)
        layout3.addWidget(self.fap_resample_widget)
        layout3.addWidget(self.fap_loudnorm_widget)

        tab3.setLayout(layout3)
        return tab3

    def create_settings_tab4(self):
        tab4 = QWidget()
        layout4 = QVBoxLayout()
        widget_registry.register(tab4, "tab4")
        self.fap_separate_widget = FAPSeparateWidget(self.console_widget, self.python)
        self.fap_sliceaudio_widget = FAPSliceAudioWidget(
            self.console_widget, self.python
        )
        self.fap_transcribe_widget = FAPTranscribeWidget(
            self.console_widget, self.python
        )
        layout4.addWidget(self.fap_separate_widget)
        layout4.addWidget(self.fap_sliceaudio_widget)
        layout4.addWidget(self.fap_transcribe_widget)
        tab4.setLayout(layout4)
        return tab4

    def create_settings_tab5(self):
        tab5 = QWidget()
        layout5 = QVBoxLayout()
        widget_registry.register(tab5, "tab5")
        self.fap_frequency_widget = FAPFrequencyStatWidget(
            self.console_widget, self.python
        )
        self.fap_lengstat_widget = FAPLengthStatWidget(self.console_widget, self.python)
        self.fap_mergelab_widget = FAPMergeLabWidget(self.console_widget, self.python)
        layout5.addWidget(self.fap_frequency_widget)
        layout5.addWidget(self.fap_lengstat_widget)
        layout5.addWidget(self.fap_mergelab_widget)
        tab5.setLayout(layout5)
        return tab5

    def create_settings_tab6(self):
        tab6 = QWidget()
        layout6 = QVBoxLayout()
        widget_registry.register(tab6, "tab6")
        self.clear_button = QPushButton(_t("console.empty"))
        self.clear_button.clicked.connect(self.console_widget.clear_console)
        layout6 = QVBoxLayout()
        layout6.addWidget(self.clear_button)
        layout6.addWidget(self.console_widget)
        tab6.setLayout(layout6)
        return tab6

    def setup_ui_settings(self, layout: QVBoxLayout):
        # we have language and backend settings in the first row
        row = QHBoxLayout()
        row.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # set up a theme combo box
        theme_label = QLabel(_t("theme.name"))
        row.addWidget(theme_label)
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

        self.language_combo.setCurrentText(language_map.get(config.locale, "en_US"))
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

        layout.addLayout(row)

    def setup_device_settings(self, layout: QVBoxLayout):
        # second row: a group box for audio device settings
        row = QGroupBox(_t("audio_device.name"))
        widget_registry.register(row, "device")
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
        row.setMaximumHeight(100)
        row.setLayout(row_layout)
        layout.addWidget(row)

    def setup_audio_settings(self, layout: QVBoxLayout):
        # third row: a group box for audio settings
        row = QGroupBox(_t("audio.name"))
        widget_registry.register(row, "audio")

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
        self.max_new_tokens_slider.setToolTip("0 means no limit")
        self.max_new_tokens_slider.setMinimum(0)
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
        self.repetition_penalty_label = QLabel(
            f"{config.repetition_penalty / 1000:.2f}"
        )
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
            self.mp3_bitrate_combo.setCurrentText(str(config.mp3_bitrate))
        else:
            # not found, use default
            self.mp3_bitrate_combo.setCurrentIndex(0)
            config.mp3_bitrate = int(self.mp3_bitrate_combo.currentText())

        row_layout.addWidget(self.mp3_bitrate_combo, 2, 4)

        row.setLayout(row_layout)
        row.setMaximumHeight(200)
        layout.addWidget(row)

    def setup_reference_settings(self, layout: QVBoxLayout):
        row = QGroupBox()
        widget_registry.register(row, "ref")
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
        self.file_list_widget.setMinimumHeight(100)
        self.file_list_widget.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
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
        layout.addWidget(row)

    def setup_textinput_settings(self, layout: QVBoxLayout):
        row = QGroupBox()
        widget_registry.register(row, "textinput")
        row.setTitle(_t("tts_input.name"))

        row_layout = QGridLayout()
        self.text_editor = TextEditorWidget()
        row_layout.addWidget(self.text_editor)
        row.setLayout(row_layout)
        layout.addWidget(row)

    def setup_audioplayer_settings(self, layout: QVBoxLayout):
        row = QGroupBox()
        widget_registry.register(row, "audioplayer")
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
        row_layout.addWidget(
            QLabel(_t("tts_output.volume") + " ↕"),
            1,
            0,
            1,
            1,
            Qt.AlignmentFlag.AlignCenter,
        )
        row_layout.addWidget(self.volume_slider, 1, 1, 1, 4)
        self.volume_label = QLabel(f"{config.volume}")
        self.volume_slider.valueChanged.connect(
            lambda v: self.volume_label.setText(f"{v}")
        )
        row_layout.addWidget(
            self.volume_label, 1, 5, 1, 1, Qt.AlignmentFlag.AlignCenter
        )
        self.play_button = QPushButton(_t("tts_output.play"))
        self.play_button.clicked.connect(self.toggle_play)
        row_layout.addWidget(self.play_button, 1, 6, 1, 2)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(50, 200)  # 50% 到 200% 的播放速率
        self.speed_slider.setValue(config.speed)  # 初始速率为 100%
        self.speed_slider.sliderMoved.connect(self.set_speed)
        row_layout.addWidget(
            QLabel(_t("tts_output.speed") + " >>"),
            2,
            0,
            1,
            1,
            Qt.AlignmentFlag.AlignCenter,
        )
        row_layout.addWidget(self.speed_slider, 2, 1, 1, 4)
        self.speed_label = QLabel(f"{config.speed / 100:.2f} x")
        self.speed_slider.valueChanged.connect(
            lambda v: self.speed_label.setText(f"{v / 100:.2f} x")
        )
        row_layout.addWidget(self.speed_label, 2, 5, 1, 1, Qt.AlignmentFlag.AlignCenter)

        self.open_button = QPushButton(_t("tts_output.open"))
        self.open_button.clicked.connect(self.open_file)
        row_layout.addWidget(self.open_button, 2, 6, 1, 2)

        self.save_audio_label = QLabel(_t("tts_output.save_audio_label"))
        row_layout.addWidget(
            self.save_audio_label, 3, 0, 1, 1, Qt.AlignmentFlag.AlignCenter
        )

        self.save_audio_path = QLineEdit()
        self.save_audio_path.setPlaceholderText(_t("tts_output.save_audio_input"))
        self.save_audio_path.setText(f"{config.save_path}")
        row_layout.addWidget(self.save_audio_path, 3, 1, 1, 4)
        row.setMaximumHeight(200)
        row.setLayout(row_layout)

        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)
        layout.addWidget(row)

    def setup_backend_settings(self, layout: QVBoxLayout):
        widget = QGroupBox()
        widget.setTitle(_t("backend.title"))
        widget_registry.register(widget, "backend")
        row = QGridLayout()

        row.addWidget(QLabel(_t("backend.python_path")), 0, 0)

        self.python.setMinimumWidth(75)
        self.python.setPlaceholderText(_t("backend.python_info"))
        self.python.setToolTip(_t("backend.python_tooltip"))
        self.python.setText("python")
        row.addWidget(self.python, 0, 1)

        self.select_py_button = QPushButton(_t("backend.select_py"))
        self.select_py_button.clicked.connect(self.select_python)
        row.addWidget(self.select_py_button, 0, 2)

        row.addWidget(QLabel(_t("backend.api_key")), 1, 0)
        self.api_key = QLineEdit()
        self.api_key.setMinimumWidth(75)
        self.api_key.setPlaceholderText(_t("backend.api_info"))
        self.api_key.setText("YOUR_API_KEY")
        row.addWidget(self.api_key, 1, 1)

        self.test_py_button = QPushButton(_t("backend.test_py"))
        self.test_py_button.clicked.connect(self.test_python)
        row.addWidget(self.test_py_button, 1, 2)

        row.addWidget(QLabel(_t("backend.name")), 2, 0)
        self.backend_input = QLineEdit()
        self.backend_input.setText(config.backend)
        row.addWidget(self.backend_input, 2, 1)

        self.test_url_button = QPushButton(_t("backend.test_url"))
        self.test_url_button.clicked.connect(self.test_backend)
        row.addWidget(self.test_url_button, 2, 2)

        widget.setLayout(row)
        widget.setMaximumHeight(150)
        layout.addWidget(widget)

    def setup_action_buttons(self, layout: QVBoxLayout):
        row = QWidget()
        row_layout = QHBoxLayout()
        widget_registry.register(row, "action_widget")

        self.now_audio = QLabel(_t("action.audio").format(audio_name="(null)"))
        row_layout.addWidget(self.now_audio)
        row_layout.addStretch(1)

        self.start_button = QPushButton(_t("action.start"))
        self.start_button.clicked.connect(self.start_conversion)
        row_layout.addWidget(self.start_button)

        self.stop_button = QPushButton(_t("action.stop"))
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_conversion)
        self.stop_button.setStyleSheet(STOP_BUTTON_QSS)
        row_layout.addWidget(self.stop_button)

        self.latency_label = QLabel(_t("action.latency").format(latency=0))
        row_layout.addWidget(self.latency_label)

        row.setMaximumHeight(100)
        row.setLayout(row_layout)
        layout.addWidget(row)

    def change_theme(self, index):
        config.theme = self.theme_combo.itemData(index)
        is_light = config.theme == "light"
        if hasattr(self, "background_label"):
            self.background_label.setVisible(is_light)

        if is_light:
            for widget in widget_registry.get_registered_widgets().values():
                self.set_widget_background(widget)
            widget_registry.get_registered_widgets().get("action_widget").setStyleSheet(
                """
                    QFrame, QWidget#action_widget { 
                        border-radius: 10px; 
                    }
                """
            )

        else:
            for widget in widget_registry.get_registered_widgets().values():
                widget.setStyleSheet("")

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
            os.execv(sys.argv[0], sys.argv)

    def upload_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Files", "", "Audio / Text (*.wav *.lab *.flac *.mp3)"
        )
        if files:
            self.files = files
            self.file_list_widget.clear()
            for file in files:
                self.file_list_widget.addItem(file)
            QMessageBox.information(
                self, "Upload Complete", f"Uploaded {len(files)} files."
            )
        else:
            QMessageBox.warning(
                self, "No Files Selected", "Please select at least one file."
            )

    def remove_files(self):
        self.files = []
        self.file_list_widget.clear()
        QMessageBox.warning(self, "Caution", "Successfully Removed References.")

    def select_python(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Select Files", "", "Python interpreter (python*.*)"
        )
        if file:
            self.python.setText(file)
            QMessageBox.information(self, "OK", f"Selected a Python interpreter.")
        else:
            self.python.setText("python")
            QMessageBox.warning(
                self, "No Python Selected", "Fallback: built-in python interpreter."
            )

    def test_python(self):
        message_box = QMessageBox()

        try:
            command = [
                self.python.text(),
                "-c",
                (
                    "import torch; "
                    "print(f'Python Version: {torch.__version__}'); "
                    "print(f'CUDA Available: {torch.cuda.is_available()}'); "
                    "print(f'Device Count: {torch.cuda.device_count()}')"
                ),
            ]
            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode == 0:
                output = result.stdout.strip()
                message_box.setIcon(QMessageBox.Icon.Information)
                message_box.setText(f"Python & CUDA Test Result:\n{output}")
            else:
                message_box.setIcon(QMessageBox.Icon.Warning)
                message_box.setText(f"Error in subprocess:\n{result.stderr}")

        except Exception as e:
            message_box.setIcon(QMessageBox.Icon.Warning)
            message_box.setText(f"Exception occurred:\n{str(e)}")

        message_box.exec()

    def test_backend(self):
        backend = self.backend_input.text()

        try:
            response = requests.options(backend, timeout=5)
        except:
            response = None

        message_box = QMessageBox()

        if response is not None and (
            response.status_code == 200 or response.status_code == 204
        ):
            message_box.setIcon(QMessageBox.Icon.Information)
            message_box.setText(_t("backend.test_succeed") + f"{response}")
            config.backend = backend
            save_config()
        else:
            message_box.setIcon(QMessageBox.Icon.Question)
            message_box.setText(_t("backend.test_failed") + f"{response}")

        message_box.exec()

    def save_config(self, save_to_file=True):
        config.backend = self.backend_input.text()
        config.input_device = self.input_device_combo.currentData()
        config.output_device = self.output_device_combo.currentData()
        config.chunk_length = self.chunk_length_slider.value()
        config.max_new_tokens = self.max_new_tokens_slider.value()
        config.top_p = self.top_p_slider.value()
        config.repetition_penalty = self.repetition_penalty_slider.value()
        config.temperature = self.temperature_slider.value()
        config.mp3_bitrate = int(self.mp3_bitrate_combo.currentText())
        config.ref_id = self.ref_id_input.text()
        config.save_path = self.save_audio_path.text()
        config.speed = self.speed_slider.value()
        config.volume = self.volume_slider.value()
        config.font_size = self.text_editor.font_size_spin.value()
        config.font_family = self.text_editor.font_combo.currentText()

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
        if len(sys.argv) == 1:
            sys.argv.insert(0, sys.executable)
        os.execv(sys.argv[0], sys.argv)

    def open_file(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, _t("tts_output.open"), "", "Audio Files (*.mp3 *.wav *.flac)"
        )
        self.set_audio(file_name)

    def set_audio(self, audio_file):
        if Path(audio_file).exists():
            self.player.setSource(QUrl.fromLocalFile(audio_file))
            self.play_button.setText(_t("tts_output.play"))
            self.now_audio.setText(_t("action.audio").format(audio_name=audio_file))

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_button.setText(_t("tts_output.play"))
        else:
            self.player.play()
            self.play_button.setText(_t("tts_output.pause"))

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
        if self.player.position() == self.player.duration():
            self.player.pause()
            self.play_button.setText(_t("tts_output.play"))

    @staticmethod
    def format_time(ms):
        seconds = (ms // 1000) % 60
        minutes = (ms // (1000 * 60)) % 60
        return f"{minutes:02}:{seconds:02}"

    def start_conversion(self):
        self.save_config(save_to_file=False)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        now = datetime.datetime.now()
        text = self.text_editor.input_edit.toPlainText()

        audio_name = now.strftime("%Y%m%d_%H%M%S")
        audio_path = Path(self.save_audio_path.text()) / f"{audio_name}.mp3"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        self.audio_path = str(audio_path)
        kwargs = dict(
            chunk_length=self.chunk_length_slider.value(),
            top_p=self.top_p_slider.value() / 1000.0,
            repetition_penalty=self.repetition_penalty_slider.value() / 1000.0,
            max_new_tokens=self.max_new_tokens_slider.value(),
            temperature=self.temperature_slider.value() / 1000.0,
            mp3_bitrate=int(self.mp3_bitrate_combo.currentText()),
        )
        self.tts_worker = TTSWorker(
            ref_files=self.files,
            ref_id=self.ref_id_input.text(),
            backend=self.backend_input.text(),
            text=text,
            api_key=self.api_key.text(),
            audio_path=str(audio_path),
            **kwargs,
        )
        self.tts_worker.finished.connect(self.on_conversion_finished)
        self.tts_worker.start()

        self.now_audio.setText(_t("action.audio").format(audio_name=str(audio_path)))

    def stop_conversion(self):
        self.tts_worker.stop()
        self.tts_worker.wait()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def on_conversion_finished(self):
        self.stop_conversion()
        self.set_audio(self.audio_path)()
