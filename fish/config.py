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
    # Service: TTS
    backend: str = "http://localhost:8080/v1/tts"
    # Service: Agent
    decoder_url: str = "http://localhost:8080/v1/vqgan"
    llm_url: str = "http://localhost:8080/v1/chat"
    proxy_url: str = "http://127.0.0.1:7890"

    system_prompt: str = 'You are a voice assistant created by Fish Audio, offering end-to-end\
 voice interaction for a seamless user experience. You are required to first transcribe\
 the user\'s speech, then answer it in the following format: "Question: [USER_SPEECH]\n\
  \nResponse: [YOUR_RESPONSE]\n"\u3002You are required to use the following voice\
 in this conversation.'

    ref_id: str = ""
    save_path: str = str(Path.cwd() / "output")
    python_path: str = (
        str(Path.cwd() / "fishenv" / "env" / "python.exe")
        if sys.platform == "win32"
        else "python"
    )

    input_device: str | None = None
    output_device: str | None = None

    mp3_bitrate: int = 64
    opus_bitrate: int = -1000

    chunk_length: int = 200
    max_new_tokens: int = 0
    top_p: int = 700
    repetition_penalty: int = 1200
    temperature: int = 700

    sample_duration: int = 1000
    fade_duration: int = 80
    extra_duration: int = 50
    input_denoise: bool = True
    output_denoise: bool = True
    sola_search_duration: int = 12
    buffer_num: int = 4

    sample_rate: int = 44100
    volume: int = 50
    speed: int = 100

    font_size: int = 10
    font_family: str = "Microsoft YaHei UI"

    # Plugins
    current_plugin: str | None = None
    plugins: dict[str, dict] = field(default_factory=dict)

    @property
    def sample_frames(self):
        return self.sample_duration * self.sample_rate // 1000

    @property
    def fade_frames(self):
        return self.fade_duration * self.sample_rate // 1000

    @property
    def extra_frames(self):
        return self.extra_duration * self.sample_rate // 1000

    @property
    def sola_search_frames(self):
        return self.sola_search_duration * self.sample_rate // 1000


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
