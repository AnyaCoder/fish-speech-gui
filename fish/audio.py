import sounddevice as sd


def get_devices(update: bool = True):
    if update:
        sd._terminate()
        sd._initialize()

    devices = sd.query_devices()
    hostapis = sd.query_hostapis()

    for hostapi in hostapis:
        for device_idx in hostapi["devices"]:
            devices[device_idx]["hostapi_name"] = hostapi["name"]

    input_devices = [
        {"id": idx, "name": f"{d['name']} ({d['hostapi_name']})"}
        for idx, d in enumerate(devices)
        if d["max_input_channels"] > 0
    ]

    output_devices = [
        {"id": idx, "name": f"{d['name']} ({d['hostapi_name']})"}
        for idx, d in enumerate(devices)
        if d["max_output_channels"] > 0
    ]

    return input_devices, output_devices

from typing import Literal, Optional
from pydantic import BaseModel

class ServeReferenceAudio(BaseModel):
    audio: bytes
    text: str


class ServeTTSRequest(BaseModel):
    text: str
    chunk_length: int = 200
    # Audio format
    format: Literal["wav", "pcm", "mp3"] = "wav"
    mp3_bitrate: Literal[64, 128, 192] = 128
    # References audios for in-context learning
    references: list[ServeReferenceAudio] = []
    # Reference id
    # For example, if you want use https://fish.audio/m/7f92f8afb8ec43bf81429cc1c9199cb1/
    # Just pass 7f92f8afb8ec43bf81429cc1c9199cb1
    reference_id: str | None = None
    # Normalize text for en & zh, this increase stability for numbers
    normalize: bool = True
    mp3_bitrate: Optional[int] = 64
    opus_bitrate: Optional[int] = -1000
    # Balance mode will reduce latency to 300ms, but may decrease stability
    latency: Literal["normal", "balanced"] = "normal"
    # not usually used below
    streaming: bool = False
    emotion: Optional[str] = None
    max_new_tokens: int = 1024
    top_p: float = 0.7
    repetition_penalty: float = 1.2
    temperature: float = 0.7
