from dataclasses import dataclass, field
from typing import Annotated, Literal

from pydantic import BaseModel
from pydantic.functional_validators import SkipValidation
from pydantic.types import conlist


class ServeVQPart(BaseModel):
    type: Literal["vq"] = "vq"
    codes: SkipValidation[list[list[int]]]


class ServeTextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ServeAudioPart(BaseModel):
    type: Literal["audio"] = "audio"
    audio: bytes


class ServeMessage(BaseModel):
    role: Literal["system", "assistant", "user"]
    parts: list[ServeVQPart | ServeTextPart]


class ServeRequest(BaseModel):
    messages: Annotated[list[ServeMessage], conlist(ServeMessage, min_length=1)]
    max_new_tokens: int = 1024
    top_p: float = 0.7
    repetition_penalty: float = 1.2
    temperature: float = 0.7
    streaming: bool = False
    num_samples: int = 1
    early_stop_threshold: float = 1.0


class ServeVQGANEncodeRequest(BaseModel):
    # The audio here should be in wav, mp3, etc
    audios: list[bytes]


class ServeVQGANEncodeResponse(BaseModel):
    tokens: SkipValidation[list[list[list[int]]]]


class ServeVQGANDecodeRequest(BaseModel):
    tokens: SkipValidation[list[list[list[int]]]]


class ServeVQGANDecodeResponse(BaseModel):
    # The audio here should be in PCM float16 format
    audios: list[bytes]
