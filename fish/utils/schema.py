from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel
from pydantic.functional_validators import SkipValidation


class ServeVQPart(BaseModel):
    type: Literal["vq"] = "vq"
    codes: SkipValidation[list[list[int]]]


class ServeTextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ServeAudioPart(BaseModel):
    type: Literal["audio"] = "audio"
    audio: bytes


@dataclass(kw_only=True)
class BasePart:
    pass
