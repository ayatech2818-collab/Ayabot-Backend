from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError


class VoiceClientMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VoiceAuthMessage(VoiceClientMessage):
    type: Literal["auth"]
    ticket: str


class VoiceAudioMessage(VoiceClientMessage):
    type: Literal["audio"]
    data: str


class VoiceTextMessage(VoiceClientMessage):
    type: Literal["text"]
    text: str


class VoiceEndMessage(VoiceClientMessage):
    type: Literal["end"]


VoiceMessage = Annotated[
    VoiceAuthMessage | VoiceAudioMessage | VoiceTextMessage | VoiceEndMessage,
    Field(discriminator="type"),
]

_voice_message_adapter = TypeAdapter(VoiceMessage)


class VoiceMessageValidationError(ValueError):
    pass


def parse_voice_message(payload: object) -> VoiceMessage:
    try:
        return _voice_message_adapter.validate_python(payload)
    except ValidationError as exc:
        raise VoiceMessageValidationError("Invalid voice message") from exc


def ready_message() -> dict:
    return {
        "type": "ready",
        "protocolVersion": 1,
        "inputAudio": {
            "encoding": "pcm_s16le",
            "sampleRate": 16000,
            "channels": 1,
        },
        "outputAudio": {
            "encoding": "pcm_s16le",
            "sampleRate": 24000,
            "channels": 1,
        },
    }


def error_message(
    message: str,
    *,
    code: str,
    recoverable: bool,
) -> dict:
    return {
        "type": "error",
        "message": message,
        "code": code,
        "recoverable": recoverable,
    }
