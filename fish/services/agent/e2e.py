import ctypes
import io
import struct
from dataclasses import dataclass
from enum import Enum
from typing import AsyncGenerator

import httpx
import numpy as np
import ormsgpack
import soundfile as sf

from fish.config import config

from .schema import ServeRequest, ServeVQGANDecodeRequest, ServeVQGANEncodeRequest


class CustomAudioFrame:
    def __init__(self, data, sample_rate, num_channels, samples_per_channel):
        if len(data) < num_channels * samples_per_channel * ctypes.sizeof(
            ctypes.c_int16
        ):
            raise ValueError(
                "data length must be >= num_channels * samples_per_channel * sizeof(int16)"
            )

        self._data = bytearray(data)
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self.samples_per_channel = samples_per_channel

    @property
    def data(self):
        return memoryview(self._data).cast("h")

    @property
    def duration(self):
        return self.samples_per_channel / self.sample_rate

    def __repr__(self):
        return (
            f"CustomAudioFrame(sample_rate={self.sample_rate}, "
            f"num_channels={self.num_channels}, "
            f"samples_per_channel={self.samples_per_channel}, "
            f"duration={self.duration:.3f})"
        )


class FishE2EEventType(Enum):
    SPEECH_SEGMENT = 1
    TEXT_SEGMENT = 2
    END_OF_TEXT = 3
    END_OF_SPEECH = 4
    ASR_RESULT = 5
    USER_CODES = 6


@dataclass
class FishE2EEvent:
    type: FishE2EEventType
    frame: CustomAudioFrame = None
    text: str = None
    vq_codes: list[list[int]] = None


class FishE2EAgent:
    client = httpx.AsyncClient(
        timeout=None,
        limits=httpx.Limits(
            max_connections=None,
            max_keepalive_connections=None,
            keepalive_expiry=None,
        ),
        proxies={
            "http://": config.proxy_url,
            "https://": config.proxy_url,
            # no proxy for local
            "http://127.0.0.1": None,
            "https://127.0.0.1": None,
            "http://localhost": None,
            "https://localhost": None,
        },
    )

    def __init__(
        self,
        llm_url: str,
        vqgan_url: str,
    ):
        self.llm_url = llm_url
        self.vqgan_url = vqgan_url

    async def get_codes(self, audio_path: str):
        # Step 1: Read audio data and sample rate from the file path
        audio_data, sample_rate = sf.read(audio_path)

        # Step 2: Write audio data to an in-memory buffer as a WAV format
        audio_buffer = io.BytesIO()
        sf.write(audio_buffer, audio_data, sample_rate, format="WAV")
        audio_buffer.seek(0)

        # Step 3: Encode audio using VQGAN
        encode_request = ServeVQGANEncodeRequest(audios=[audio_buffer.read()])
        encode_request_bytes = ormsgpack.packb(
            encode_request, option=ormsgpack.OPT_SERIALIZE_PYDANTIC
        )
        encode_response = await FishE2EAgent.client.post(
            f"{self.vqgan_url}/encode",
            data=encode_request_bytes,
            headers={"Content-Type": "application/msgpack"},
        )
        encode_response_data = ormsgpack.unpackb(encode_response.content)
        codes = encode_response_data["tokens"][0]

        return codes

    async def stream(
        self,
        chat_ctx: dict,
    ) -> AsyncGenerator[FishE2EEvent, None]:
        messages = chat_ctx.get("messages", None)
        if not messages:
            return

        request = ServeRequest(
            messages=messages,
            streaming=True,
            num_samples=1,
        )

        # Step 3: Stream LLM response and decode audio
        buffer = b""
        vq_codes = []
        current_vq = False

        async def decode_send():
            nonlocal current_vq
            nonlocal vq_codes

            data = np.concatenate(vq_codes, axis=1).tolist()
            # Decode VQ codes to audio
            decode_request = ServeVQGANDecodeRequest(tokens=[data])
            decode_response = await self.client.post(
                f"{self.vqgan_url}/decode",
                data=ormsgpack.packb(
                    decode_request,
                    option=ormsgpack.OPT_SERIALIZE_PYDANTIC,
                ),
                headers={"Content-Type": "application/msgpack"},
            )
            decode_data = ormsgpack.unpackb(decode_response.content)

            # Convert float16 audio data to int16
            audio_data = np.frombuffer(decode_data["audios"][0], dtype=np.float16)
            audio_data = (audio_data * 32767).astype(np.int16).tobytes()

            audio_frame = CustomAudioFrame(
                data=audio_data,
                samples_per_channel=len(audio_data) // 2,
                sample_rate=44100,
                num_channels=1,
            )

            yield FishE2EEvent(
                type=FishE2EEventType.SPEECH_SEGMENT,
                frame=audio_frame,
                vq_codes=data,
            )

            current_vq = False
            vq_codes = []

        async with self.client.stream(
            "POST",
            self.llm_url,
            data=ormsgpack.packb(request, option=ormsgpack.OPT_SERIALIZE_PYDANTIC),
            headers={"Content-Type": "application/msgpack"},
        ) as response:
            async for chunk in response.aiter_bytes():
                buffer += chunk

                while len(buffer) >= 4:
                    read_length = struct.unpack("I", buffer[:4])[0]
                    if len(buffer) < 4 + read_length:
                        break

                    body = buffer[4 : 4 + read_length]
                    buffer = buffer[4 + read_length :]
                    data = ormsgpack.unpackb(body)

                    if data["delta"] and data["delta"]["part"]:
                        if current_vq and data["delta"]["part"]["type"] == "text":
                            async for event in decode_send():
                                yield event
                        if data["delta"]["part"]["type"] == "text":
                            yield FishE2EEvent(
                                type=FishE2EEventType.TEXT_SEGMENT,
                                text=data["delta"]["part"]["text"],
                            )
                        elif data["delta"]["part"]["type"] == "vq":
                            vq_codes.append(np.array(data["delta"]["part"]["codes"]))
                            current_vq = True

        if current_vq and vq_codes:
            async for event in decode_send():
                yield event

        yield FishE2EEvent(type=FishE2EEventType.END_OF_TEXT)
        yield FishE2EEvent(type=FishE2EEventType.END_OF_SPEECH)
