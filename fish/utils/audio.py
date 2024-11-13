import io
import wave

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


def wav_chunk_header(sample_rate=44100, bit_depth=16, channels=1):
    buffer = io.BytesIO()

    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(bit_depth // 8)
        wav_file.setframerate(sample_rate)

    wav_header_bytes = buffer.getvalue()
    buffer.close()
    return wav_header_bytes
