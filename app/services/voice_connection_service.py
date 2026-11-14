import asyncio
import base64
import binascii
import logging
import math
import time
from array import array
from dataclasses import dataclass
from sys import byteorder
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect
from google.genai import types

from app.core.config import Settings, get_settings
from app.schemas.voice import (
    VoiceAudioMessage,
    VoiceAuthMessage,
    VoiceEndMessage,
    VoiceMessageValidationError,
    VoiceTextMessage,
    parse_voice_message,
    ready_message,
)
from app.services.gemini_live_service import execute_gemini_function_call


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VoiceRuntimeLimits:
    idle_timeout_seconds: float
    max_duration_seconds: float
    tool_timeout_seconds: float
    max_text_chars: int
    max_audio_bytes: int
    input_queue_max_messages: int
    output_queue_max_messages: int
    audio_activity_rms_threshold: int

    @classmethod
    def from_settings(cls, settings: Settings) -> "VoiceRuntimeLimits":
        return cls(
            idle_timeout_seconds=settings.voice_session_idle_timeout_seconds,
            max_duration_seconds=settings.voice_session_max_duration_seconds,
            tool_timeout_seconds=settings.voice_tool_timeout_seconds,
            max_text_chars=settings.voice_max_text_chars,
            max_audio_bytes=settings.voice_max_audio_bytes,
            input_queue_max_messages=settings.voice_input_queue_max_messages,
            output_queue_max_messages=settings.voice_output_queue_max_messages,
            audio_activity_rms_threshold=(
                settings.voice_audio_activity_rms_threshold
            ),
        )


class VoiceConnectionError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        recoverable: bool,
        close_code: int,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.recoverable = recoverable
        self.close_code = close_code


@dataclass(frozen=True)
class _GeminiInput:
    kind: str
    payload: bytes | str


class _ActivityTracker:
    def __init__(self) -> None:
        self._last_user_activity = time.monotonic()
        self._changed = asyncio.Event()

    def mark_user_activity(self) -> None:
        self._last_user_activity = time.monotonic()
        self._changed.set()

    async def wait_until_idle(self, timeout_seconds: float) -> None:
        while True:
            self._changed.clear()
            observed = self._last_user_activity
            remaining = timeout_seconds - (time.monotonic() - observed)

            if remaining <= 0:
                return

            try:
                await asyncio.wait_for(
                    self._changed.wait(),
                    timeout=remaining,
                )
            except TimeoutError:
                if self._last_user_activity == observed:
                    return


class GeminiToolCoordinator:
    def __init__(
        self,
        *,
        session,
        product_id: UUID,
        send_lock: asyncio.Lock,
        timeout_seconds: float,
    ) -> None:
        self._session = session
        self._product_id = product_id
        self._send_lock = send_lock
        self._timeout_seconds = timeout_seconds
        self._tasks: dict[str, asyncio.Task] = {}
        self._failures: asyncio.Queue[BaseException] = asyncio.Queue()
        self._anonymous_call_number = 0

    def start(self, tool_call) -> None:
        for function_call in tool_call.function_calls:
            call_id = function_call.id

            if not call_id:
                self._anonymous_call_number += 1
                call_id = f"anonymous-{self._anonymous_call_number}"

            existing = self._tasks.pop(call_id, None)
            if existing is not None:
                existing.cancel()

            task = asyncio.create_task(
                self._execute_and_respond(function_call),
                name=f"voice-tool-{call_id}",
            )
            self._tasks[call_id] = task
            task.add_done_callback(
                lambda completed, key=call_id: self._tool_done(
                    key,
                    completed,
                )
            )

    def cancel(self, call_ids: list[str]) -> None:
        for call_id in call_ids:
            task = self._tasks.pop(call_id, None)
            if task is not None:
                task.cancel()

    async def wait_for_failure(self) -> None:
        failure = await self._failures.get()
        raise failure

    async def close(self) -> None:
        tasks = list(self._tasks.values())
        self._tasks.clear()

        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_and_respond(self, function_call) -> None:
        response = await execute_gemini_function_call(
            function_call,
            self._product_id,
            timeout_seconds=self._timeout_seconds,
        )

        async with self._send_lock:
            await self._session.send_tool_response(
                function_responses=[response],
            )

    def _tool_done(self, call_id: str, task: asyncio.Task) -> None:
        if self._tasks.get(call_id) is task:
            self._tasks.pop(call_id, None)

        if task.cancelled():
            return

        exception = task.exception()
        if exception is not None:
            self._failures.put_nowait(exception)


def _pcm16_rms(audio_bytes: bytes) -> float:
    if not audio_bytes or len(audio_bytes) % 2:
        return 0.0

    samples = array("h")
    samples.frombytes(audio_bytes)

    if byteorder != "little":
        samples.byteswap()

    mean_square = sum(sample * sample for sample in samples) / len(samples)
    return math.sqrt(mean_square)


def _decode_audio(encoded_audio: str, limits: VoiceRuntimeLimits) -> bytes:
    maximum_encoded_length = ((limits.max_audio_bytes + 2) // 3) * 4

    if not encoded_audio or len(encoded_audio) > maximum_encoded_length:
        raise VoiceConnectionError(
            code="message_too_large",
            message="Audio message is too large.",
            recoverable=False,
            close_code=1009,
        )

    try:
        audio_bytes = base64.b64decode(
            encoded_audio,
            validate=True,
        )
    except (ValueError, binascii.Error) as exc:
        raise VoiceConnectionError(
            code="invalid_message",
            message="Audio message is invalid.",
            recoverable=False,
            close_code=1008,
        ) from exc

    if (
        not audio_bytes
        or len(audio_bytes) > limits.max_audio_bytes
        or len(audio_bytes) % 2
    ):
        raise VoiceConnectionError(
            code="invalid_message",
            message="Audio message is invalid.",
            recoverable=False,
            close_code=1008,
        )

    return audio_bytes


def _queue_nowait(queue: asyncio.Queue, item, *, direction: str) -> None:
    try:
        queue.put_nowait(item)
    except asyncio.QueueFull as exc:
        raise VoiceConnectionError(
            code="connection_overloaded",
            message="Voice connection cannot keep up with audio traffic.",
            recoverable=True,
            close_code=1013,
        ) from exc

    logger.debug("Queued voice message: direction=%s", direction)


async def _receive_from_browser(
    websocket: WebSocket,
    input_queue: asyncio.Queue[_GeminiInput],
    activity: _ActivityTracker,
    limits: VoiceRuntimeLimits,
) -> None:
    while True:
        try:
            payload = await websocket.receive_json()
            message = parse_voice_message(payload)
        except WebSocketDisconnect:
            raise
        except VoiceMessageValidationError as exc:
            raise VoiceConnectionError(
                code="invalid_message",
                message="Voice message is invalid.",
                recoverable=False,
                close_code=1008,
            ) from exc
        except Exception as exc:
            raise VoiceConnectionError(
                code="invalid_message",
                message="Voice message is invalid.",
                recoverable=False,
                close_code=1008,
            ) from exc

        if isinstance(message, VoiceAuthMessage):
            raise VoiceConnectionError(
                code="invalid_message",
                message="Voice session is already authenticated.",
                recoverable=False,
                close_code=1008,
            )

        if isinstance(message, VoiceEndMessage):
            return

        if isinstance(message, VoiceTextMessage):
            text = message.text.strip()

            if not text or len(text) > limits.max_text_chars:
                raise VoiceConnectionError(
                    code="invalid_message",
                    message="Text message is invalid.",
                    recoverable=False,
                    close_code=1008,
                )

            activity.mark_user_activity()
            _queue_nowait(
                input_queue,
                _GeminiInput(kind="text", payload=text),
                direction="browser-to-gemini",
            )
            continue

        if isinstance(message, VoiceAudioMessage):
            audio_bytes = _decode_audio(message.data, limits)

            if _pcm16_rms(audio_bytes) >= limits.audio_activity_rms_threshold:
                activity.mark_user_activity()

            _queue_nowait(
                input_queue,
                _GeminiInput(kind="audio", payload=audio_bytes),
                direction="browser-to-gemini",
            )


async def _send_to_gemini(
    session,
    input_queue: asyncio.Queue[_GeminiInput],
    send_lock: asyncio.Lock,
) -> None:
    while True:
        message = await input_queue.get()

        async with send_lock:
            if message.kind == "audio":
                await session.send_realtime_input(
                    audio=types.Blob(
                        data=message.payload,
                        mime_type="audio/pcm;rate=16000",
                    )
                )
            else:
                await session.send_client_content(
                    turns=types.Content(
                        role="user",
                        parts=[types.Part(text=message.payload)],
                    ),
                    turn_complete=True,
                )


def _queue_output(
    output_queue: asyncio.Queue[dict],
    message: dict,
) -> None:
    _queue_nowait(
        output_queue,
        message,
        direction="gemini-to-browser",
    )


async def _receive_from_gemini(
    session,
    output_queue: asyncio.Queue[dict],
    activity: _ActivityTracker,
    tool_coordinator: GeminiToolCoordinator,
) -> None:
    while True:
        received_message = False

        async for response in session.receive():
            received_message = True

            if response.tool_call:
                tool_coordinator.start(response.tool_call)

            if response.tool_call_cancellation:
                tool_coordinator.cancel(
                    list(response.tool_call_cancellation.ids or []),
                )

            if response.go_away:
                raise VoiceConnectionError(
                    code="gemini_connection_failed",
                    message="Voice service is temporarily unavailable.",
                    recoverable=True,
                    close_code=1013,
                )

            if response.voice_activity or response.voice_activity_detection_signal:
                activity.mark_user_activity()

            server_content = response.server_content
            if not server_content:
                continue

            if server_content.input_transcription:
                text = server_content.input_transcription.text
                if text:
                    activity.mark_user_activity()
                    _queue_output(
                        output_queue,
                        {"type": "input_transcription", "text": text},
                    )

            if server_content.output_transcription:
                text = server_content.output_transcription.text
                if text:
                    _queue_output(
                        output_queue,
                        {"type": "output_transcription", "text": text},
                    )

            if server_content.model_turn:
                for part in server_content.model_turn.parts:
                    inline_data = part.inline_data
                    if not inline_data or not inline_data.data:
                        continue

                    if (
                        inline_data.mime_type
                        and not inline_data.mime_type.startswith("audio/")
                    ):
                        continue

                    _queue_output(
                        output_queue,
                        {
                            "type": "audio",
                            "data": base64.b64encode(
                                inline_data.data,
                            ).decode("ascii"),
                            "mimeType": "audio/pcm;rate=24000",
                        },
                    )

            if server_content.interrupted:
                _queue_output(output_queue, {"type": "interrupted"})

            if server_content.turn_complete:
                _queue_output(output_queue, {"type": "turn_complete"})

        # google-genai 2.34 receive() covers one complete model turn. An
        # empty iterator means the underlying Live connection ended.
        if not received_message:
            return


async def _send_to_browser(
    websocket: WebSocket,
    output_queue: asyncio.Queue[dict],
) -> None:
    while True:
        await websocket.send_json(await output_queue.get())


async def _idle_watchdog(
    activity: _ActivityTracker,
    timeout_seconds: float,
) -> None:
    await activity.wait_until_idle(timeout_seconds)
    raise VoiceConnectionError(
        code="session_idle_timeout",
        message="Voice session ended after a period of inactivity.",
        recoverable=True,
        close_code=1000,
    )


async def _duration_watchdog(timeout_seconds: float) -> None:
    await asyncio.sleep(timeout_seconds)
    raise VoiceConnectionError(
        code="session_max_duration",
        message="Voice session reached its maximum duration.",
        recoverable=True,
        close_code=1000,
    )


async def run_voice_connection(
    *,
    websocket: WebSocket,
    session,
    product_id: UUID,
    limits: VoiceRuntimeLimits | None = None,
) -> None:
    runtime_limits = limits or VoiceRuntimeLimits.from_settings(
        get_settings()
    )
    input_queue: asyncio.Queue[_GeminiInput] = asyncio.Queue(
        maxsize=runtime_limits.input_queue_max_messages,
    )
    output_queue: asyncio.Queue[dict] = asyncio.Queue(
        maxsize=runtime_limits.output_queue_max_messages,
    )
    activity = _ActivityTracker()
    send_lock = asyncio.Lock()
    tool_coordinator = GeminiToolCoordinator(
        session=session,
        product_id=product_id,
        send_lock=send_lock,
        timeout_seconds=runtime_limits.tool_timeout_seconds,
    )

    await websocket.send_json(ready_message())

    tasks = {
        "browser_receiver": asyncio.create_task(
            _receive_from_browser(
                websocket,
                input_queue,
                activity,
                runtime_limits,
            ),
            name="voice-browser-receiver",
        ),
        "gemini_sender": asyncio.create_task(
            _send_to_gemini(session, input_queue, send_lock),
            name="voice-gemini-sender",
        ),
        "gemini_receiver": asyncio.create_task(
            _receive_from_gemini(
                session,
                output_queue,
                activity,
                tool_coordinator,
            ),
            name="voice-gemini-receiver",
        ),
        "browser_sender": asyncio.create_task(
            _send_to_browser(websocket, output_queue),
            name="voice-browser-sender",
        ),
        "idle_watchdog": asyncio.create_task(
            _idle_watchdog(
                activity,
                runtime_limits.idle_timeout_seconds,
            ),
            name="voice-idle-watchdog",
        ),
        "duration_watchdog": asyncio.create_task(
            _duration_watchdog(runtime_limits.max_duration_seconds),
            name="voice-duration-watchdog",
        ),
        "tool_failure": asyncio.create_task(
            tool_coordinator.wait_for_failure(),
            name="voice-tool-failure-watchdog",
        ),
    }

    try:
        done, _ = await asyncio.wait(
            set(tasks.values()),
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in done:
            task.result()

        if tasks["gemini_receiver"] in done:
            raise VoiceConnectionError(
                code="gemini_connection_failed",
                message="Voice service connection ended unexpectedly.",
                recoverable=True,
                close_code=1013,
            )
    finally:
        for task in tasks.values():
            if not task.done():
                task.cancel()

        await asyncio.gather(*tasks.values(), return_exceptions=True)
        await tool_coordinator.close()
