import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from fish.modules.console import ConsoleWidget
from fish.modules.globals import FAP, LINE_ALLOC, STOP_BUTTON_QSS
from fish.modules.registry import widget_registry
from fish.modules.task import TaskManagerMixin
from fish.utils.i18n import _t


class FAPToWavWidget(TaskManagerMixin):
    def __init__(self, console_widget: ConsoleWidget, python: QLineEdit):
        super().__init__(console_widget, name=_t("FAPToWavWidget.name"))
        layout = QVBoxLayout(self)
        self.setup_fap_to_wav_settings(layout)
        self.setLayout(layout)
        self.python = python

    def setup_fap_to_wav_settings(self, layout: QVBoxLayout):
        row = QGroupBox(_t("FAPToWavWidget.title"))
        widget_registry.register(row, "fap_to_wav")
        row_layout = QGridLayout()
        row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        row_layout.addWidget(QLabel(_t("task.input_dir.name")), 0, *LINE_ALLOC[0][0])
        row_layout.addWidget(self.input_dir, 0, *LINE_ALLOC[0][1])
        input_browse_button = QPushButton(_t("task.browse"))
        input_browse_button.clicked.connect(self.browse_input_dir)
        row_layout.addWidget(input_browse_button, 0, *LINE_ALLOC[0][2])

        row_layout.addWidget(QLabel(_t("task.output_dir.name")), 1, *LINE_ALLOC[1][0])
        row_layout.addWidget(self.output_dir, 1, *LINE_ALLOC[1][1])
        output_browse_button = QPushButton(_t("task.browse"))
        output_browse_button.clicked.connect(self.browse_output_dir)
        row_layout.addWidget(output_browse_button, 1, *LINE_ALLOC[1][2])

        row_layout.addWidget(
            QLabel(_t("FAPToWavWidget.max_length")), 2, *LINE_ALLOC[2][0]
        )
        self.segment_spin = QSpinBox()
        self.segment_spin.setRange(0, 60 * 60)
        self.segment_spin.setValue(0)
        row_layout.addWidget(self.segment_spin, 2, *LINE_ALLOC[2][1])

        self.recursive_check = QCheckBox(_t("FAPWidget.rc"))
        self.recursive_check.setChecked(True)
        row_layout.addWidget(self.recursive_check, 3, *LINE_ALLOC[3][0])

        self.overwrite_check = QCheckBox(_t("FAPWidget.oc"))
        self.overwrite_check.setChecked(False)
        row_layout.addWidget(self.overwrite_check, 3, *LINE_ALLOC[3][1])

        self.clean_check = QCheckBox(_t("FAPWidget.cc"))
        self.clean_check.setChecked(False)
        row_layout.addWidget(self.clean_check, 3, *LINE_ALLOC[3][2])

        self.start_button.clicked.connect(self.call_to_wav)
        row_layout.addWidget(self.start_button, 4, *LINE_ALLOC[3][0])

        self.stop_button.clicked.connect(self.stop_to_wav)
        row_layout.addWidget(self.stop_button, 4, *LINE_ALLOC[3][1])
        row_layout.addWidget(self.progress_bar, 4, *LINE_ALLOC[3][2])

        row.setLayout(row_layout)
        layout.addWidget(row)

    def call_to_wav(self):
        input_dir = self.input_dir.text()
        output_dir = self.output_dir.text()

        if not input_dir or not Path(input_dir).is_dir():
            QMessageBox.warning(
                self,
                _t("task.input_dir.error_title"),
                _t("task.input_dir.error_msg"),
            )
            return
        if not output_dir or not Path(output_dir).is_dir():
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        segment = str(self.segment_spin.value())
        recursive = (
            "--recursive" if self.recursive_check.isChecked() else "--no-recursive"
        )
        overwrite = (
            "--overwrite" if self.overwrite_check.isChecked() else "--no-overwrite"
        )
        clean = "--clean" if self.clean_check.isChecked() else "--no-clean"
        python = self.python.text().strip()
        prefix = [
            python,
            *FAP,
            "to-wav",
        ]
        args = [
            input_dir,
            output_dir,
            "--segment",
            segment,
            recursive,
            overwrite,
            clean,
        ]

        self.start_task(prefix + args)

    def stop_to_wav(self):
        self.stop_task()


class FAPResampleWidget(TaskManagerMixin):
    def __init__(self, console_widget: ConsoleWidget, python: QLineEdit):
        super().__init__(console_widget, name=_t("FAPResampleWidget.name"))
        layout = QVBoxLayout(self)
        self.setup_fap_resample_settings(layout)
        self.setLayout(layout)
        self.python = python

    def setup_fap_resample_settings(self, layout: QVBoxLayout):
        row = QGroupBox(_t("FAPResampleWidget.title"))
        widget_registry.register(row, "fap_resample")
        row_layout = QGridLayout()
        row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        row_layout.addWidget(QLabel(_t("task.input_dir.name")), 0, *LINE_ALLOC[0][0])
        row_layout.addWidget(self.input_dir, 0, *LINE_ALLOC[0][1])
        input_browse_button = QPushButton(_t("task.browse"))
        input_browse_button.clicked.connect(self.browse_input_dir)
        row_layout.addWidget(input_browse_button, 0, *LINE_ALLOC[0][2])

        row_layout.addWidget(QLabel(_t("task.output_dir.name")), 1, *LINE_ALLOC[1][0])
        row_layout.addWidget(self.output_dir, 1, *LINE_ALLOC[1][1])
        output_browse_button = QPushButton(_t("task.browse"))
        output_browse_button.clicked.connect(self.browse_output_dir)
        row_layout.addWidget(output_browse_button, 1, *LINE_ALLOC[1][2])

        row_layout.addWidget(
            QLabel(_t("FAPResampleWidget.sampling_rate")), 2, *LINE_ALLOC[2][0]
        )
        self.sampling_rate_combo = QComboBox()
        self.sampling_rate_combo.addItems(["44100", "22050", "16000", "8000"])
        self.sampling_rate_combo.setCurrentText("44100")
        row_layout.addWidget(self.sampling_rate_combo, 2, *LINE_ALLOC[2][1])

        row_layout.addWidget(
            QLabel(_t("FAPResampleWidget.num_workers")), 2, *LINE_ALLOC[2][2]
        )
        self.num_workers_spin = QSpinBox()
        self.num_workers_spin.setRange(1, 64)
        self.num_workers_spin.setValue(4)
        row_layout.addWidget(self.num_workers_spin, 2, *LINE_ALLOC[2][3])

        self.recursive_check = QCheckBox(_t("FAPWidget.rc"))
        self.recursive_check.setChecked(True)
        row_layout.addWidget(self.recursive_check, 3, *LINE_ALLOC[3][0])

        self.overwrite_check = QCheckBox(_t("FAPWidget.oc"))
        self.overwrite_check.setChecked(False)
        row_layout.addWidget(self.overwrite_check, 3, *LINE_ALLOC[3][1])

        self.clean_check = QCheckBox(_t("FAPWidget.cc"))
        self.clean_check.setChecked(False)
        row_layout.addWidget(self.clean_check, 3, *LINE_ALLOC[3][2])

        self.start_button.clicked.connect(self.call_resample)
        row_layout.addWidget(self.start_button, 4, *LINE_ALLOC[3][0])

        self.stop_button.clicked.connect(self.stop_resample)
        row_layout.addWidget(self.stop_button, 4, *LINE_ALLOC[3][1])
        row_layout.addWidget(self.progress_bar, 4, *LINE_ALLOC[3][2])

        row.setLayout(row_layout)
        layout.addWidget(row)

    def call_resample(self):
        input_dir = self.input_dir.text()
        output_dir = self.output_dir.text()

        if not input_dir or not Path(input_dir).is_dir():
            QMessageBox.warning(
                self,
                _t("task.input_dir.error_title"),
                _t("task.input_dir.error_msg"),
            )
            return
        if not output_dir or not Path(output_dir).is_dir():
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        sr = self.sampling_rate_combo.currentText()
        recursive = (
            "--recursive" if self.recursive_check.isChecked() else "--no-recursive"
        )
        overwrite = (
            "--overwrite" if self.overwrite_check.isChecked() else "--no-overwrite"
        )
        clean = "--clean" if self.clean_check.isChecked() else "--no-clean"
        num_workers = str(self.num_workers_spin.value())
        python = self.python.text().strip()
        prefix = [
            python,
            *FAP,
            "resample",
        ]
        args = [
            input_dir,
            output_dir,
            "-sr",
            sr,
            recursive,
            overwrite,
            clean,
            "--mono",
            "--num-workers",
            num_workers,
        ]

        self.start_task(prefix + args)

    def stop_resample(self):
        self.stop_task()


class FAPLoudNormWidget(TaskManagerMixin):
    def __init__(self, console_widget: ConsoleWidget, python: QLineEdit):
        super().__init__(console_widget, name=_t("FAPLoudNormWidget.name"))
        layout = QVBoxLayout(self)
        self.setup_fap_loud_norm_settings(layout)
        self.setLayout(layout)
        self.python = python

    def setup_fap_loud_norm_settings(self, layout: QVBoxLayout):
        row = QGroupBox(_t("FAPLoudNormWidget.title"))
        widget_registry.register(row, "fap_loud_norm")
        row_layout = QGridLayout()
        row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Input Dir
        row_layout.addWidget(QLabel(_t("task.input_dir.name")), 0, *LINE_ALLOC[0][0])
        row_layout.addWidget(self.input_dir, 0, *LINE_ALLOC[0][1])
        input_browse_button = QPushButton(_t("task.browse"))
        input_browse_button.setToolTip(_t("task.input_dir.tooltip"))
        input_browse_button.clicked.connect(self.browse_input_dir)
        row_layout.addWidget(input_browse_button, 0, *LINE_ALLOC[0][2])

        # Output Directory
        row_layout.addWidget(QLabel(_t("task.output_dir.name")), 1, *LINE_ALLOC[1][0])
        row_layout.addWidget(self.output_dir, 1, *LINE_ALLOC[1][1])
        output_browse_button = QPushButton(_t("task.browse"))
        output_browse_button.setToolTip(_t("task.output_dir.tooltip"))
        output_browse_button.clicked.connect(self.browse_output_dir)
        row_layout.addWidget(output_browse_button, 1, *LINE_ALLOC[1][2])

        # Peak Normalize
        row_layout.addWidget(QLabel(_t("FAPLoudNormWidget.peak")), 2, *LINE_ALLOC[2][0])
        self.peak_spin = QDoubleSpinBox()
        self.peak_spin.setRange(-100.0, 0.0)
        self.peak_spin.setValue(-1.0)
        self.peak_spin.setToolTip(_t("FAPLoudNormWidget.peak_tooltip"))
        row_layout.addWidget(self.peak_spin, 2, *LINE_ALLOC[2][1])

        # Loudness Normalize
        row_layout.addWidget(
            QLabel(_t("FAPLoudNormWidget.loudness")), 2, *LINE_ALLOC[2][2]
        )
        self.loudness_spin = QDoubleSpinBox()
        self.loudness_spin.setRange(-100.0, 0.0)
        self.loudness_spin.setValue(-23.0)
        self.loudness_spin.setToolTip(_t("FAPLoudNormWidget.loudness_tooltip"))
        row_layout.addWidget(self.loudness_spin, 2, *LINE_ALLOC[2][3])

        # Block Size
        row_layout.addWidget(
            QLabel(_t("FAPLoudNormWidget.block_size")), 3, *LINE_ALLOC[2][0]
        )
        self.block_size_spin = QDoubleSpinBox()
        self.block_size_spin.setRange(0.1, 10.0)
        self.block_size_spin.setValue(0.4)
        self.block_size_spin.setToolTip(_t("FAPLoudNormWidget.block_size_tooltip"))
        row_layout.addWidget(self.block_size_spin, 3, *LINE_ALLOC[2][1])

        # Number of Workers
        row_layout.addWidget(
            QLabel(_t("FAPLoudNormWidget.workers")), 3, *LINE_ALLOC[2][2]
        )
        self.num_workers_spin = QSpinBox()
        self.num_workers_spin.setRange(1, 64)
        self.num_workers_spin.setValue(32)
        self.num_workers_spin.setToolTip(_t("FAPLoudNormWidget.workers_tooltip"))
        row_layout.addWidget(self.num_workers_spin, 3, *LINE_ALLOC[2][3])

        # Recursive Check
        self.recursive_check = QCheckBox(_t("FAPWidget.rc"))
        self.recursive_check.setChecked(True)
        row_layout.addWidget(self.recursive_check, 4, *LINE_ALLOC[3][0])

        # Overwrite Check
        self.overwrite_check = QCheckBox(_t("FAPWidget.oc"))
        self.overwrite_check.setChecked(False)
        row_layout.addWidget(self.overwrite_check, 4, *LINE_ALLOC[3][1])

        # Clean Check
        self.clean_check = QCheckBox(_t("FAPWidget.cc"))
        self.clean_check.setChecked(False)
        row_layout.addWidget(self.clean_check, 4, *LINE_ALLOC[3][2])

        # Start Button
        self.start_button.setToolTip(_t("FAPLoudNormWidget.start_tooltip"))
        self.start_button.clicked.connect(self.call_loud_norm)
        row_layout.addWidget(self.start_button, 5, *LINE_ALLOC[3][0])

        # Stop Button
        self.stop_button.setStyleSheet(STOP_BUTTON_QSS)
        self.stop_button.setToolTip(_t("FAPLoudNormWidget.stop_tooltip"))
        self.stop_button.clicked.connect(self.stop_loud_norm)
        self.stop_button.setEnabled(False)
        row_layout.addWidget(self.stop_button, 5, *LINE_ALLOC[3][1])
        row_layout.addWidget(self.progress_bar, 5, *LINE_ALLOC[3][2])

        row.setLayout(row_layout)
        layout.addWidget(row)

    def call_loud_norm(self):
        input_dir = self.input_dir.text()
        output_dir = self.output_dir.text()

        if not input_dir or not Path(input_dir).is_dir():
            QMessageBox.warning(
                self,
                _t("task.input_dir.error_title"),
                _t("task.input_dir.error_msg"),
            )
            return
        if not output_dir or not Path(output_dir).is_dir():
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        peak = str(self.peak_spin.value())
        loudness = str(self.loudness_spin.value())
        block_size = str(self.block_size_spin.value())
        recursive = (
            "--recursive" if self.recursive_check.isChecked() else "--no-recursive"
        )
        overwrite = (
            "--overwrite" if self.overwrite_check.isChecked() else "--no-overwrite"
        )
        clean = "--clean" if self.clean_check.isChecked() else "--no-clean"
        num_workers = str(self.num_workers_spin.value())
        python = self.python.text().strip()
        prefix = [
            python,
            *FAP,
            "loudness-norm",
        ]
        args = [
            input_dir,
            output_dir,
            "--peak",
            peak,
            "--loudness",
            loudness,
            "--block-size",
            block_size,
            recursive,
            overwrite,
            clean,
            "--num-workers",
            num_workers,
        ]

        self.start_task(prefix + args)

    def stop_loud_norm(self):
        self.stop_task()


class FAPSeparateWidget(TaskManagerMixin):
    def __init__(self, console_widget: ConsoleWidget, python: QLineEdit):
        super().__init__(console_widget, name=_t("FAPSeparateWidget.name"))
        layout = QVBoxLayout(self)
        self.setup_fap_separate_settings(layout)
        self.setLayout(layout)
        self.python = python

    def setup_fap_separate_settings(self, layout: QVBoxLayout):
        row = QGroupBox(_t("FAPSeparateWidget.title"))
        widget_registry.register(row, "fap_separate")
        row_layout = QGridLayout()
        row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        row_layout.addWidget(QLabel(_t("task.input_dir.name")), 0, *LINE_ALLOC[0][0])
        row_layout.addWidget(self.input_dir, 0, *LINE_ALLOC[0][1])
        input_browse_button = QPushButton(_t("task.browse"))
        input_browse_button.clicked.connect(self.browse_input_dir)
        row_layout.addWidget(input_browse_button, 0, *LINE_ALLOC[0][2])

        row_layout.addWidget(QLabel(_t("task.output_dir.name")), 1, *LINE_ALLOC[1][0])
        row_layout.addWidget(self.output_dir, 1, *LINE_ALLOC[1][1])
        output_browse_button = QPushButton(_t("task.browse"))
        output_browse_button.clicked.connect(self.browse_output_dir)
        row_layout.addWidget(output_browse_button, 1, *LINE_ALLOC[1][2])

        # Track
        row_layout.addWidget(
            QLabel(_t("FAPSeparateWidget.track")), 2, *LINE_ALLOC[2][0]
        )
        self.track_combo = QComboBox()
        self.track_combo.addItems(["vocals", "drums", "bass", "other"])
        self.track_combo.setCurrentText("vocals")
        row_layout.addWidget(self.track_combo, 2, *LINE_ALLOC[2][1])

        # Model
        row_layout.addWidget(
            QLabel(_t("FAPSeparateWidget.model")), 2, *LINE_ALLOC[2][2]
        )
        self.model_combo = QComboBox()
        self.model_combo.addItems(["htdemucs", "demucs", "tasnet"])
        self.model_combo.setCurrentText("htdemucs")
        row_layout.addWidget(self.model_combo, 2, *LINE_ALLOC[2][3])

        # Shifts
        row_layout.addWidget(
            QLabel(_t("FAPSeparateWidget.shifts")), 3, *LINE_ALLOC[2][0]
        )
        self.shifts_spin = QSpinBox()
        self.shifts_spin.setRange(1, 10)
        self.shifts_spin.setValue(1)
        row_layout.addWidget(self.shifts_spin, 3, *LINE_ALLOC[2][1])

        # Workers per GPU
        row_layout.addWidget(
            QLabel(_t("FAPSeparateWidget.workers_per_gpu")), 3, *LINE_ALLOC[2][2]
        )
        self.num_workers_per_gpu_spin = QSpinBox()
        self.num_workers_per_gpu_spin.setRange(1, 8)
        self.num_workers_per_gpu_spin.setValue(2)
        row_layout.addWidget(self.num_workers_per_gpu_spin, 3, *LINE_ALLOC[2][3])

        # Other options
        self.recursive_check = QCheckBox(_t("FAPWidget.rc"))
        self.recursive_check.setChecked(True)
        row_layout.addWidget(self.recursive_check, 4, *LINE_ALLOC[3][0])

        self.overwrite_check = QCheckBox(_t("FAPWidget.oc"))
        self.overwrite_check.setChecked(False)
        row_layout.addWidget(self.overwrite_check, 4, *LINE_ALLOC[3][1])

        self.clean_check = QCheckBox(_t("FAPWidget.cc"))
        self.clean_check.setChecked(False)
        row_layout.addWidget(self.clean_check, 4, *LINE_ALLOC[3][2])

        # Start and Stop buttons
        self.start_button.clicked.connect(self.call_separate)
        row_layout.addWidget(self.start_button, 5, *LINE_ALLOC[3][0])

        self.stop_button.setStyleSheet(STOP_BUTTON_QSS)
        self.stop_button.clicked.connect(self.stop_separate)
        self.stop_button.setEnabled(False)
        row_layout.addWidget(self.stop_button, 5, *LINE_ALLOC[3][1])
        row_layout.addWidget(self.progress_bar, 5, *LINE_ALLOC[3][2])

        row.setLayout(row_layout)
        layout.addWidget(row)

    def call_separate(self):
        input_dir = self.input_dir.text()
        output_dir = self.output_dir.text()

        if not input_dir or not Path(input_dir).is_dir():
            QMessageBox.warning(
                self,
                _t("task.input_dir.error_title"),
                _t("task.input_dir.error_msg"),
            )
            return
        if not output_dir or not Path(output_dir).is_dir():
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        track = self.track_combo.currentText()
        model = self.model_combo.currentText()
        shifts = str(self.shifts_spin.value())
        workers_per_gpu = str(self.num_workers_per_gpu_spin.value())
        recursive = (
            "--recursive" if self.recursive_check.isChecked() else "--no-recursive"
        )
        overwrite = (
            "--overwrite" if self.overwrite_check.isChecked() else "--no-overwrite"
        )
        clean = "--clean" if self.clean_check.isChecked() else "--no-clean"
        python = self.python.text().strip()
        prefix = [
            python,
            *FAP,
            "separate",
        ]
        args = [
            input_dir,
            output_dir,
            "--track",
            track,
            "--model",
            model,
            "--shifts",
            shifts,
            "--num_workers_per_gpu",
            workers_per_gpu,
            recursive,
            overwrite,
            clean,
        ]
        self.start_task(prefix + args)

    def stop_separate(self):
        self.stop_task()


class FAPSliceAudioWidget(TaskManagerMixin):
    def __init__(self, console_widget: ConsoleWidget, python: QLineEdit):
        super().__init__(console_widget, name=_t("FAPSliceAudioWidget.name"))
        layout = QVBoxLayout(self)
        self.setup_fap_slice_settings(layout)
        self.setLayout(layout)
        self.python = python

    def setup_fap_slice_settings(self, layout: QVBoxLayout):
        row = QGroupBox(_t("FAPSliceAudioWidget.title"))
        widget_registry.register(row, "fap_slice")
        row_layout = QGridLayout()
        row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Input Directory
        row_layout.addWidget(QLabel(_t("task.input_dir.name")), 0, *LINE_ALLOC[0][0])
        row_layout.addWidget(self.input_dir, 0, *LINE_ALLOC[0][1])
        input_browse_button = QPushButton(_t("task.browse"))
        input_browse_button.clicked.connect(self.browse_input_dir)
        row_layout.addWidget(input_browse_button, 0, *LINE_ALLOC[0][2])

        # Output Directory
        row_layout.addWidget(QLabel(_t("task.output_dir.name")), 1, *LINE_ALLOC[1][0])
        row_layout.addWidget(self.output_dir, 1, *LINE_ALLOC[1][1])
        output_browse_button = QPushButton(_t("task.browse"))
        output_browse_button.clicked.connect(self.browse_output_dir)
        row_layout.addWidget(output_browse_button, 1, *LINE_ALLOC[1][2])

        # Min Duration
        row_layout.addWidget(
            QLabel(_t("FAPSliceAudioWidget.min_duration")), 2, *LINE_ALLOC[4][0]
        )
        self.min_duration_spin = QDoubleSpinBox()
        self.min_duration_spin.setRange(0.1, 100.0)
        self.min_duration_spin.setValue(0.5)
        row_layout.addWidget(self.min_duration_spin, 2, *LINE_ALLOC[4][1])

        # Max Duration
        row_layout.addWidget(
            QLabel(_t("FAPSliceAudioWidget.max_duration")), 2, *LINE_ALLOC[4][2]
        )
        self.max_duration_spin = QDoubleSpinBox()
        self.max_duration_spin.setRange(1.0, 600.0)
        self.max_duration_spin.setValue(20.0)
        row_layout.addWidget(self.max_duration_spin, 2, *LINE_ALLOC[4][3])

        # Min Silence Duration
        row_layout.addWidget(
            QLabel(_t("FAPSliceAudioWidget.min_silence")), 2, *LINE_ALLOC[4][4]
        )
        self.min_silence_spin = QDoubleSpinBox()
        self.min_silence_spin.setRange(0.1, 10.0)
        self.min_silence_spin.setValue(0.3)
        row_layout.addWidget(self.min_silence_spin, 2, *LINE_ALLOC[4][5])

        # Number of Workers
        row_layout.addWidget(
            QLabel(_t("FAPSliceAudioWidget.workers")), 3, *LINE_ALLOC[2][0]
        )
        self.num_workers_spin = QSpinBox()
        self.num_workers_spin.setRange(1, 64)
        self.num_workers_spin.setValue(1)
        row_layout.addWidget(self.num_workers_spin, 3, *LINE_ALLOC[2][1])

        # Speech Pad Duration
        row_layout.addWidget(
            QLabel(_t("FAPSliceAudioWidget.speech_pad")), 3, *LINE_ALLOC[2][2]
        )
        self.speech_pad_spin = QDoubleSpinBox()
        self.speech_pad_spin.setRange(0.0, 5.0)
        self.speech_pad_spin.setValue(0.1)
        row_layout.addWidget(self.speech_pad_spin, 3, *LINE_ALLOC[2][3])

        # Recursive Check
        self.recursive_check = QCheckBox(_t("FAPWidget.rc"))
        self.recursive_check.setChecked(True)
        row_layout.addWidget(self.recursive_check, 4, *LINE_ALLOC[3][0])

        # Overwrite Check
        self.overwrite_check = QCheckBox(_t("FAPWidget.oc"))
        self.overwrite_check.setChecked(False)
        row_layout.addWidget(self.overwrite_check, 4, *LINE_ALLOC[3][1])

        # Clean Check
        self.clean_check = QCheckBox(_t("FAPWidget.cc"))
        self.clean_check.setChecked(False)
        row_layout.addWidget(self.clean_check, 4, *LINE_ALLOC[3][2])

        # Flat Layout Check
        self.flat_layout_check = QCheckBox(_t("FAPSliceAudioWidget.flat_layout"))
        self.flat_layout_check.setChecked(False)
        row_layout.addWidget(self.flat_layout_check, 5, *LINE_ALLOC[3][0])

        # Merge Short Check
        self.merge_short_check = QCheckBox(_t("FAPSliceAudioWidget.merge_short"))
        self.merge_short_check.setChecked(False)
        row_layout.addWidget(self.merge_short_check, 5, *LINE_ALLOC[3][1])

        # Start and Stop Buttons
        self.start_button.clicked.connect(self.call_slice_audio)
        row_layout.addWidget(self.start_button, 6, *LINE_ALLOC[3][0])

        self.stop_button.setStyleSheet(STOP_BUTTON_QSS)
        self.stop_button.clicked.connect(self.stop_slice_audio)
        self.stop_button.setEnabled(False)
        row_layout.addWidget(self.stop_button, 6, *LINE_ALLOC[3][1])
        row_layout.addWidget(self.progress_bar, 6, *LINE_ALLOC[3][2])

        row.setLayout(row_layout)
        layout.addWidget(row)

    def call_slice_audio(self):
        input_dir = self.input_dir.text()
        output_dir = self.output_dir.text()

        if not input_dir or not Path(input_dir).is_dir():
            QMessageBox.warning(
                self,
                _t("task.input_dir.error_title"),
                _t("task.input_dir.error_msg"),
            )
            return
        if not output_dir or not Path(output_dir).is_dir():
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        num_workers = str(self.num_workers_spin.value())
        min_duration = str(self.min_duration_spin.value())
        max_duration = str(self.max_duration_spin.value())
        min_silence_duration = str(self.min_silence_spin.value())
        speech_pad_duration = str(self.speech_pad_spin.value())
        recursive = (
            "--recursive" if self.recursive_check.isChecked() else "--no-recursive"
        )
        overwrite = (
            "--overwrite" if self.overwrite_check.isChecked() else "--no-overwrite"
        )
        clean = "--clean" if self.clean_check.isChecked() else "--no-clean"
        flat_layout = (
            "--flat-layout"
            if self.flat_layout_check.isChecked()
            else "--no-flat-layout"
        )
        merge_short = (
            "--merge-short"
            if self.merge_short_check.isChecked()
            else "--no-merge-short"
        )
        python = self.python.text().strip()
        prefix = [
            python,
            *FAP,
            "slice-audio-v3",
        ]
        args = [
            input_dir,
            output_dir,
            "--num-workers",
            num_workers,
            "--min-duration",
            min_duration,
            "--max-duration",
            max_duration,
            "--min-silence-duration",
            min_silence_duration,
            "--speech-pad-duration",
            speech_pad_duration,
            recursive,
            overwrite,
            clean,
            flat_layout,
            merge_short,
        ]
        self.start_task(prefix + args)

    def stop_slice_audio(self):
        self.stop_task()


class FAPTranscribeWidget(TaskManagerMixin):
    def __init__(self, console_widget: ConsoleWidget, python: QLineEdit):
        super().__init__(console_widget, name=_t("FAPTranscribeWidget.name"))
        layout = QVBoxLayout(self)
        self.setup_fap_transcribe_settings(layout)
        self.setLayout(layout)
        self.python = python

    def setup_fap_transcribe_settings(self, layout: QVBoxLayout):
        row = QGroupBox(_t("FAPTranscribeWidget.title"))
        widget_registry.register(row, "fap_transcribe")
        row_layout = QGridLayout()
        row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Input Directory
        row_layout.addWidget(QLabel(_t("task.input_dir.name")), 0, 0, 1, 1)
        row_layout.addWidget(self.input_dir, 0, 1, 1, 5)
        input_browse_button = QPushButton(_t("task.browse"))
        input_browse_button.clicked.connect(self.browse_input_dir)
        row_layout.addWidget(input_browse_button, 0, 6, 1, 2)

        # Number of Workers
        row_layout.addWidget(
            QLabel(_t("FAPTranscribeWidget.workers")), 1, *LINE_ALLOC[2][0]
        )
        self.num_workers_spin = QSpinBox()
        self.num_workers_spin.setRange(1, 64)
        self.num_workers_spin.setValue(1)
        row_layout.addWidget(self.num_workers_spin, 1, *LINE_ALLOC[2][1])

        # Language
        row_layout.addWidget(
            QLabel(_t("FAPTranscribeWidget.language")), 1, *LINE_ALLOC[2][2]
        )
        self.language_combo = QComboBox()
        self.language_combo.addItems(["zh", "en", "fr", "de", "es"])
        self.language_combo.setCurrentText("zh")
        row_layout.addWidget(self.language_combo, 1, *LINE_ALLOC[2][3])

        # Model Size
        row_layout.addWidget(
            QLabel(_t("FAPTranscribeWidget.model_size")), 2, *LINE_ALLOC[2][0]
        )
        self.model_size_combo = QComboBox()
        self.model_size_combo.addItems(
            ["small", "medium", "large", "iic/SenseVoiceSmall"]
        )
        self.model_size_combo.setCurrentText("iic/SenseVoiceSmall")
        row_layout.addWidget(self.model_size_combo, 2, *LINE_ALLOC[2][1])

        # Model Type
        row_layout.addWidget(
            QLabel(_t("FAPTranscribeWidget.model_type")), 2, *LINE_ALLOC[2][2]
        )
        self.model_type_combo = QComboBox()
        self.model_type_combo.addItems(["whisper", "funasr"])
        self.model_type_combo.setCurrentText("funasr")
        row_layout.addWidget(self.model_type_combo, 2, *LINE_ALLOC[2][3])

        # Compute Type
        row_layout.addWidget(
            QLabel(_t("FAPTranscribeWidget.compute_type")), 3, *LINE_ALLOC[4][0]
        )
        self.compute_type_combo = QComboBox()
        self.compute_type_combo.addItems(["float16", "float32", "int8", "int8_float16"])
        self.compute_type_combo.setCurrentText("float16")
        row_layout.addWidget(self.compute_type_combo, 3, *LINE_ALLOC[4][1])

        # Batch Size
        row_layout.addWidget(
            QLabel(_t("FAPTranscribeWidget.batch_size")), 3, *LINE_ALLOC[4][2]
        )
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 1024)
        self.batch_size_spin.setValue(1)
        row_layout.addWidget(self.batch_size_spin, 3, *LINE_ALLOC[4][3])

        # Recursive Check
        self.recursive_check = QCheckBox(_t("FAPWidget.rc"))
        self.recursive_check.setChecked(True)
        row_layout.addWidget(self.recursive_check, 3, *LINE_ALLOC[4][4])

        # Start and Stop Buttons
        self.start_button.clicked.connect(self.call_transcribe)
        row_layout.addWidget(self.start_button, 4, *LINE_ALLOC[3][0])

        self.stop_button.setStyleSheet(STOP_BUTTON_QSS)
        self.stop_button.clicked.connect(self.stop_transcribe)
        self.stop_button.setEnabled(False)
        row_layout.addWidget(self.stop_button, 4, *LINE_ALLOC[3][1])
        row_layout.addWidget(self.progress_bar, 4, *LINE_ALLOC[3][2])

        row.setLayout(row_layout)
        layout.addWidget(row)

    def call_transcribe(self):
        input_dir = self.input_dir.text()

        if not input_dir or not Path(input_dir).is_dir():
            QMessageBox.warning(
                self,
                _t("task.input_dir.error_title"),
                _t("task.input_dir.error_msg"),
            )
            return

        num_workers = str(self.num_workers_spin.value())
        language = self.language_combo.currentText()
        model_size = self.model_size_combo.currentText()
        model_type = self.model_type_combo.currentText()
        compute_type = self.compute_type_combo.currentText()
        batch_size = str(self.batch_size_spin.value())
        recursive = (
            "--recursive" if self.recursive_check.isChecked() else "--no-recursive"
        )
        python = self.python.text().strip()
        prefix = [
            python,
            *FAP,
            "transcribe",
        ]
        args = [
            input_dir,
            "--num-workers",
            num_workers,
            "--lang",
            language,
            "--model-type",
            model_type,
            "--batch-size",
            batch_size,
            recursive,
        ]

        if model_type == "whisper":
            args += [
                "--compute-type",
                compute_type,
                "--model-size",
                model_size,
            ]

        self.start_task(prefix + args)

    def stop_transcribe(self):
        self.stop_task()


class FAPLengthStatWidget(TaskManagerMixin):
    def __init__(self, console_widget: ConsoleWidget, python: QLineEdit):
        super().__init__(console_widget, name=_t("FAPLengthStatWidget.name"))
        layout = QVBoxLayout(self)
        self.setup_fap_length_settings(layout)
        self.setLayout(layout)
        self.python = python

    def setup_fap_length_settings(self, layout: QVBoxLayout):
        row = QGroupBox(_t("FAPLengthStatWidget.title"))
        widget_registry.register(row, "fap_length")
        row_layout = QGridLayout()
        row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Input Directory
        row_layout.addWidget(QLabel(_t("task.input_dir.name")), 0, *LINE_ALLOC[0][0])
        row_layout.addWidget(self.input_dir, 0, *LINE_ALLOC[0][1])
        input_browse_button = QPushButton(_t("task.browse"))
        input_browse_button.clicked.connect(self.browse_input_dir)
        row_layout.addWidget(input_browse_button, 0, *LINE_ALLOC[0][2])

        # Recursive Search Checkbox
        self.recursive_check = QCheckBox(_t("FAPWidget.rc"))
        self.recursive_check.setChecked(True)
        row_layout.addWidget(self.recursive_check, 1, *LINE_ALLOC[1][0])

        # Visualization Option
        self.visualize_check = QCheckBox(_t("FAPLengthStatWidget.visualize"))
        self.visualize_check.setChecked(True)
        row_layout.addWidget(self.visualize_check, 1, *LINE_ALLOC[1][1])

        # Accurate Mode Checkbox
        self.accurate_check = QCheckBox(_t("FAPLengthStatWidget.accurate"))
        self.accurate_check.setChecked(False)
        row_layout.addWidget(self.accurate_check, 1, *LINE_ALLOC[1][2])

        # Long Threshold
        row_layout.addWidget(
            QLabel(_t("FAPLengthStatWidget.long_threshold")), 2, *LINE_ALLOC[4][0]
        )
        self.long_threshold_spin = QSpinBox()
        self.long_threshold_spin.setRange(1, 3600)
        self.long_threshold_spin.setValue(300)
        row_layout.addWidget(self.long_threshold_spin, 2, *LINE_ALLOC[4][1])

        # Short Threshold
        row_layout.addWidget(
            QLabel(_t("FAPLengthStatWidget.short_threshold")), 2, *LINE_ALLOC[4][2]
        )
        self.short_threshold_spin = QSpinBox()
        self.short_threshold_spin.setRange(1, 300)
        self.short_threshold_spin.setValue(30)
        row_layout.addWidget(self.short_threshold_spin, 2, *LINE_ALLOC[4][3])

        # Number of Workers
        row_layout.addWidget(
            QLabel(_t("FAPLengthStatWidget.workers")), 2, *LINE_ALLOC[4][4]
        )
        self.num_workers_spin = QSpinBox()
        self.num_workers_spin.setRange(1, 64)
        self.num_workers_spin.setValue(4)
        row_layout.addWidget(self.num_workers_spin, 2, *LINE_ALLOC[4][5])

        # Start and Stop Buttons
        self.start_button.clicked.connect(self.call_fap_length)
        row_layout.addWidget(self.start_button, 3, *LINE_ALLOC[3][0])

        self.stop_button.clicked.connect(self.stop_fap_length)
        row_layout.addWidget(self.stop_button, 3, *LINE_ALLOC[3][1])
        row_layout.addWidget(self.progress_bar, 3, *LINE_ALLOC[3][2])

        row.setLayout(row_layout)
        layout.addWidget(row)

    def call_fap_length(self):
        input_dir = self.input_dir.text()
        if not input_dir or not Path(input_dir).is_dir():
            QMessageBox.warning(
                self,
                _t("task.input_dir.error_title"),
                _t("task.input_dir.error_msg"),
            )
            return

        recursive = (
            "--recursive" if self.recursive_check.isChecked() else "--no-recursive"
        )
        visualize = (
            "--visualize" if self.visualize_check.isChecked() else "--no-visualize"
        )
        accurate = "--accurate" if self.accurate_check.isChecked() else "--no-accurate"
        long_threshold = str(self.long_threshold_spin.value())
        short_threshold = str(self.short_threshold_spin.value())
        num_workers = str(self.num_workers_spin.value())
        python = self.python.text().strip()
        # Construct the command
        prefix = [
            python,
            *FAP,
            "length",
        ]
        args = [
            input_dir,
            recursive,
            visualize,
            accurate,
            "-l",
            long_threshold,
            "-s",
            short_threshold,
            "-w",
            num_workers,
        ]

        self.start_task(prefix + args)

    def stop_fap_length(self):
        self.stop_task()


class FAPFrequencyStatWidget(TaskManagerMixin):
    def __init__(self, console_widget: ConsoleWidget, python: QLineEdit):
        super().__init__(console_widget, name=_t("FAPFrequencyStatWidget.name"))
        layout = QVBoxLayout(self)
        self.setup_fap_frequency_settings(layout)
        self.setLayout(layout)
        self.python = python

    def setup_fap_frequency_settings(self, layout: QVBoxLayout):
        row = QGroupBox(_t("FAPFrequencyStatWidget.title"))
        widget_registry.register(row, "fap_frequency")
        row_layout = QGridLayout()
        row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Input Directory
        row_layout.addWidget(QLabel(_t("task.input_dir.name")), 0, *LINE_ALLOC[0][0])
        row_layout.addWidget(self.input_dir, 0, *LINE_ALLOC[0][1])
        input_browse_button = QPushButton(_t("task.browse"))
        input_browse_button.clicked.connect(self.browse_input_dir)
        row_layout.addWidget(input_browse_button, 0, *LINE_ALLOC[0][2])

        # Recursive Search Checkbox
        self.recursive_check = QCheckBox(_t("FAPWidget.rc"))
        self.recursive_check.setChecked(True)
        row_layout.addWidget(self.recursive_check, 1, *LINE_ALLOC[1][0])

        # Visualization Option
        self.visualize_check = QCheckBox(_t("FAPFrequencyStatWidget.visualize"))
        self.visualize_check.setChecked(True)
        row_layout.addWidget(self.visualize_check, 1, *LINE_ALLOC[1][1])

        # Number of Workers
        row_layout.addWidget(
            QLabel(_t("FAPFrequencyStatWidget.workers")), 2, *LINE_ALLOC[2][0]
        )
        self.num_workers_spin = QSpinBox()
        self.num_workers_spin.setRange(1, 64)
        self.num_workers_spin.setValue(4)
        row_layout.addWidget(self.num_workers_spin, 2, *LINE_ALLOC[2][1])

        # Start and Stop Buttons
        self.start_button.clicked.connect(self.call_fap_frequency)
        row_layout.addWidget(self.start_button, 3, *LINE_ALLOC[3][0])

        self.stop_button.clicked.connect(self.stop_fap_frequency)
        row_layout.addWidget(self.stop_button, 3, *LINE_ALLOC[3][1])
        row_layout.addWidget(self.progress_bar, 3, *LINE_ALLOC[3][2])

        row.setLayout(row_layout)
        layout.addWidget(row)

    def call_fap_frequency(self):
        input_dir = self.input_dir.text()
        if not input_dir or not Path(input_dir).is_dir():
            QMessageBox.warning(
                self,
                _t("task.input_dir.error_title"),
                _t("task.input_dir.error_msg"),
            )
            return

        recursive = (
            "--recursive" if self.recursive_check.isChecked() else "--no-recursive"
        )
        visualize = (
            "--visualize" if self.visualize_check.isChecked() else "--no-visualize"
        )
        num_workers = str(self.num_workers_spin.value())
        python = self.python.text().strip()
        # Construct the command
        prefix = [
            python,
            *FAP,
            "frequency",
        ]
        args = [
            input_dir,
            recursive,
            visualize,
            "--num-workers",
            num_workers,
        ]

        self.start_task(prefix + args)

    def stop_fap_frequency(self):
        self.stop_task()


class FAPMergeLabWidget(TaskManagerMixin):
    def __init__(self, console_widget: ConsoleWidget, python: QLineEdit):
        super().__init__(console_widget, name=_t("FAPMergeLabWidget.name"))
        layout = QVBoxLayout(self)
        self.setup_fap_merge_settings(layout)
        self.setLayout(layout)
        self.python = python

    def setup_fap_merge_settings(self, layout: QVBoxLayout):
        row = QGroupBox(_t("FAPMergeLabWidget.title"))
        widget_registry.register(row, "fap_merge_lab")
        row_layout = QGridLayout()
        row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Input Directory
        row_layout.addWidget(QLabel(_t("task.input_dir.name")), 0, *LINE_ALLOC[0][0])
        row_layout.addWidget(self.input_dir, 0, *LINE_ALLOC[0][1])
        input_browse_button = QPushButton(_t("task.browse"))
        input_browse_button.clicked.connect(self.browse_input_dir)
        row_layout.addWidget(input_browse_button, 0, *LINE_ALLOC[0][2])

        # Output FilePath
        row_layout.addWidget(
            QLabel(_t("FAPMergeLabWidget.output_filepath")), 1, *LINE_ALLOC[1][0]
        )
        self.output_dir.setPlaceholderText(
            _t("FAPMergeLabWidget.output_placeholder").format(name=self.name)
        )
        row_layout.addWidget(self.output_dir, 1, *LINE_ALLOC[1][1])
        output_browse_button = QPushButton(_t("task.browse"))
        output_browse_button.clicked.connect(self.browse_output_dir)
        row_layout.addWidget(output_browse_button, 1, *LINE_ALLOC[1][2])

        # Template
        row_layout.addWidget(
            QLabel(_t("FAPMergeLabWidget.template")), 2, *LINE_ALLOC[2][0]
        )
        self.template = QLineEdit()
        self.template.setText("{PATH}|speaker|EN|{TEXT}")
        row_layout.addWidget(self.template, 2, *LINE_ALLOC[2][1])

        # Recursive Check
        self.recursive_check = QCheckBox(_t("FAPWidget.rc"))
        self.recursive_check.setChecked(True)
        row_layout.addWidget(self.recursive_check, 2, *LINE_ALLOC[2][2])

        # Start and Stop Buttons
        self.start_button.clicked.connect(self.call_merge_lab)
        row_layout.addWidget(self.start_button, 3, *LINE_ALLOC[3][0])

        self.stop_button.clicked.connect(self.stop_merge_lab)
        row_layout.addWidget(self.stop_button, 3, *LINE_ALLOC[3][1])
        row_layout.addWidget(self.progress_bar, 3, *LINE_ALLOC[3][2])

        row.setLayout(row_layout)
        layout.addWidget(row)

    def call_merge_lab(self):
        input_dir = self.input_dir.text()
        output_file = self.output_dir.text()
        template = self.template.text()

        if not input_dir or not Path(input_dir).is_dir():
            QMessageBox.warning(
                self,
                _t("task.input_dir.error_title"),
                _t("task.input_dir.error_msg"),
            )
            return

        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        recursive = (
            "--recursive" if self.recursive_check.isChecked() else "--no-recursive"
        )
        python = self.python.text().strip()
        prefix = [
            python,
            *FAP,
            "merge-lab",
        ]
        args = [input_dir, output_file, template, recursive]
        self.start_task(prefix + args)

    def stop_merge_lab(self):
        self.stop_task()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FAPResampleWidget()
    window.resize(800, 800)
    window.show()
    sys.exit(app.exec())
