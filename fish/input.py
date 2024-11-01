import re
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFontComboBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fish.config import config
from fish.utils.i18n import _t

# Add more emotions with corresponding emojis and lighter background colors
emotions = {
    "happy": {"emoji": "😄", "color": "#ccffcc"},  # Light green
    "sad": {"emoji": "😢", "color": "#ffffcc"},  # Light yellow
    "angry": {"emoji": "😡", "color": "#ffcccc"},  # Light red
    "surprised": {"emoji": "😲", "color": "#cce5ff"},  # Light blue
    "neutral": {"emoji": "😐", "color": "#f2f2f2"},  # Light gray
}


class EmotionSelector(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t("emo_selector.name"))
        self.setLayout(QVBoxLayout())

        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText(_t("emo_selector.placeholder"))
        self.search_box.textChanged.connect(self.filter_emotions)
        self.layout().addWidget(self.search_box)

        self.list_widget = QListWidget(self)
        self.emotions = [
            " [INST]happy[/INST]",
            " [INST]sad[/INST]",
            " [INST]angry[/INST]",
            " [INST]surprised[/INST]",
            " [INST]neutral[/INST]",
        ]
        self.list_widget.addItems(self.emotions)
        self.list_widget.itemDoubleClicked.connect(self.select_emotion)
        self.layout().addWidget(self.list_widget)

        self.select_button = QPushButton("Select")
        self.select_button.clicked.connect(self.select_emotion)
        self.layout().addWidget(self.select_button)

    def filter_emotions(self):
        search_text = self.search_box.text().lower()
        self.list_widget.clear()
        filtered_emotions = [
            emotion for emotion in self.emotions if search_text in emotion.lower()
        ]
        self.list_widget.addItems(filtered_emotions)

    def select_emotion(self, item):
        if isinstance(item, bool):
            current_item = self.list_widget.currentItem()
            if current_item is not None:
                self.parent().insert_completion(current_item.text())
        else:
            self.parent().insert_completion(item.text())

        self.close()


class TextEditorWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.input_edit = QTextEdit()
        self.input_edit.setAcceptRichText(False)
        self.input_edit.setMinimumHeight(150)
        self.input_edit.setPlaceholderText(_t("text_editor.input_help"))
        layout.addWidget(self.input_edit)

        self.display_edit = QTextEdit()
        self.display_edit.setAcceptRichText(True)
        self.display_edit.setPlaceholderText(_t("text_editor.rich_help"))
        self.display_edit.setMinimumHeight(150)
        self.display_edit.setReadOnly(True)
        layout.addWidget(self.display_edit)

        font_layout = QGridLayout()

        self.checkbox = QCheckBox(_t("text_editor.rich_effect"))
        self.checkbox.setChecked(True)

        font_layout.addWidget(self.checkbox, 0, 0, 1, 2, Qt.AlignmentFlag.AlignCenter)

        font_layout.addWidget(
            QLabel(_t("text_editor.font_family")),
            0,
            2,
            1,
            1,
            Qt.AlignmentFlag.AlignCenter,
        )
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentText(config.font_family)
        font_layout.addWidget(self.font_combo, 0, 3, 1, 3)

        font_layout.addWidget(
            QLabel(_t("text_editor.font_size")),
            0,
            6,
            1,
            1,
            Qt.AlignmentFlag.AlignCenter,
        )
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setValue(config.font_size)
        font_layout.addWidget(self.font_size_spin, 0, 7, 1, 3)

        layout.addLayout(font_layout)

        self.checkbox.stateChanged.connect(self.toggle_display)
        self.input_edit.textChanged.connect(self.update_display)
        self.emotion_selector = EmotionSelector(self)

        self.update_display()

    def toggle_display(self, state):
        if state == 2:
            self.display_edit.setVisible(True)
            self.update_display()
        else:
            self.display_edit.setVisible(False)

    def update_display(self):
        text = (
            self.input_edit.toPlainText().replace("\n", "<br>").replace(" ", "&nbsp;")
        )

        def replace_emotion(match):
            emotion = match.group(1)
            if emotion in emotions:
                data = emotions[emotion]
                following_text = match.group(2)
                return (
                    f'<span style="background-color: {data["color"]}; color: black;">'
                    f'{data["emoji"]} {following_text}</span>'
                )
            return match.group(0)  # return raw text

        # 修改正则表达式，捕获后续文本
        pattern = r"\[INST\](.*?)\[\/INST\](.*?)(?=\[INST\]|$|<br>)"
        text = re.sub(pattern, replace_emotion, text, flags=re.DOTALL)

        self.display_edit.setHtml(text)

        # Apply the selected font and size
        font = self.font_combo.currentFont()
        font.setPointSize(self.font_size_spin.value())
        self.display_edit.setFont(font)

    def keyPressEvent(self, event):
        if (
            event.modifiers() == Qt.KeyboardModifier.ControlModifier
            and event.key() == Qt.Key.Key_M
        ):
            self.emotion_selector.exec()
            return

        self.input_edit.keyPressEvent(event)

    def insert_completion(self, completion):
        cursor = self.input_edit.textCursor()
        cursor.insertText(completion)
        self.input_edit.setTextCursor(cursor)
        self.update_display()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TextEditorWidget()
    window.resize(400, 400)
    window.show()
    sys.exit(app.exec())
