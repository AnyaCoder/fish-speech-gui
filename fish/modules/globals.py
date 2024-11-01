LINE_ALLOC = [
    [(0, 1, 1), (1, 1, 4), (5, 1, 2)],
    [(0, 1, 1), (1, 1, 4), (5, 1, 2)],
    [(0, 1, 1), (1, 1, 3), (4, 1, 1), (5, 1, 2)],
    [(0, 1, 2), (2, 1, 2), (4, 1, 2), (6, 1, 2)],
    [(0, 1, 1), (1, 1, 1), (2, 1, 1), (3, 1, 1), (4, 1, 1), (5, 1, 1)],
]

STOP_BUTTON_QSS = """
    QPushButton {
        background-color: transparent;
        color: red;
        border: 1px solid red;
        border-radius: 5px;
        padding: 5px 10px;
    }
    QPushButton:hover {
        background-color: rgba(255, 0, 0, 0.1);
        color: darkred;
    }
    QPushButton:pressed {
        background-color: rgba(255, 0, 0, 0.2); 
        color: darkred;
    }
"""

FAP = ["-m", "fish_audio_preprocess.cli.__main__"]
