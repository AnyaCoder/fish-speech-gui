import locale
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

if getattr(sys, "frozen", False):
    # If the application is run as a bundle, the PyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = Path(sys._MEIPASS)
else:
    application_path = Path(__file__).parent.parent


@dataclass
class Config:
    theme: Literal["auto", "light", "dark"] = "auto"
    locale: str = locale.getdefaultlocale()[0]
    backend: str = "http://localhost:8080/v1/tts"
    ref_id: str = ""
    save_path: str = str(Path.cwd() / "output")

    input_device: str | None = None
    output_device: str | None = None

    mp3_bitrate: int = 64
    opus_bitrate: int = -1000

    chunk_length: int = 200
    max_new_tokens: int = 0
    top_p: int = 700
    repetition_penalty: int = 1200
    temperature: int = 700

    sample_rate: int = 44100
    volume: int = 50
    speed: int = 100

    font_size: int = 10
    font_family: str = "Microsoft YaHei UI"

    # Plugins
    current_plugin: str | None = None
    plugins: dict[str, dict] = field(default_factory=dict)


default_config_path = str((Path.home() / ".fish" / "config.yaml").absolute())
config = Config()


def load_config(path: Path | str = default_config_path) -> Config:
    global config

    path = Path(path)

    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = Config(**yaml.safe_load(f.read()))
        except Exception:
            config = Config()
            print("Failed to load config file, use default config instead.")

    return config


def save_config(path: Path | str = default_config_path) -> None:
    path = Path(path)

    if not path.parent.exists():
        path.parent.mkdir(parents=True)

    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config.__dict__, f)


# Auto load config
load_config()
save_config()
