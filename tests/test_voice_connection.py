import asyncio
import base64
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import WebSocketDisconnect
from google.genai import types

from app.schemas.voice import (
    VoiceMessageValidationError,
    parse_voice_message,
    ready_message,
)
from app.services.voice_connection_service import (
    GeminiToolCoordinator,
    VoiceConnectionError,
    VoiceRuntimeLimits,
    _ActivityTracker,
    _decode_audio,
    _receive_from_gemini,
    run_voice_connection,
)


def runtime_limits(**overrides) -> VoiceRuntimeLimits:
    values = {
        "idle_timeout_seconds": 1,
        "max_duration_seconds": 1,
        "tool_timeout_seconds": 1,
        "max_text_chars": 4096,
        "max_audio_bytes": 32768,
        "input_queue_max_messages": 10,
        "output_queue_max_messages": 10,
        "audio_activity_rms_threshold": 200,
    }
    values.update(overrides)
    return VoiceRuntimeLimits(**values)


class FakeToolCoordinator:
    def __init__(self) -> None:
        self.started = []
        self.cancelled = []

    def start(self, tool_call) -> None:
        self.started.append(tool_call)

    def cancel(self, call_ids) -> None:
        self.cancelled.extend(call_ids)


class MultiTurnGeminiSession:
    def __init__(self, turns) -> None:
        self.turns = list(turns)
        self.receive_calls = 0

    def receive(self):
        self.receive_calls += 1
        messages = self.turns.pop(0) if self.turns else []

        async def iterator():
            for message in messages:
                yield message

        return iterator()


class HangingGeminiSession:
    async def send_realtime_input(self, **kwargs) -> None:
        pass

    async def send_client_content(self, **kwargs) -> None:
        pass

    async def send_tool_response(self, **kwargs) -> None:
        pass

    def receive(self):
        async def iterator():
            await asyncio.Event().wait()
            if False:
                yield None

        return iterator()


class DisconnectingWebSocket:
    def __init__(self) -> None:
        self.sent = []

    async def send_json(self, message) -> None:
        self.sent.append(message)

    async def receive_json(self):
        raise WebSocketDisconnect(code=1000)


class HangingWebSocket:
    def __init__(self) -> None:
        self.sent = []

    async def send_json(self, message) -> None:
        self.sent.append(message)

    async def receive_json(self):
        await asyncio.Event().wait()


class RecordingToolSession:
    def __init__(self) -> None:
        self.responses = []

    async def send_tool_response(self, **kwargs) -> None:
        self.responses.append(kwargs)


class VoiceProtocolTests(unittest.TestCase):
    def test_protocol_parses_existing_messages(self) -> None:
        auth = parse_voice_message({"type": "auth", "ticket": "t"})
        self.assertEqual(auth.ticket, "t")
        self.assertEqual(
            parse_voice_message({"type": "audio", "data": "AA=="}).type,
            "audio",
        )
        self.assertEqual(
            parse_voice_message({"type": "text", "text": "hello"}).type,
            "text",
        )
        self.assertEqual(parse_voice_message({"type": "end"}).type, "end")

    def test_protocol_rejects_unknown_or_extra_fields(self) -> None:
        with self.assertRaises(VoiceMessageValidationError):
            parse_voice_message({"type": "unknown"})

        with self.assertRaises(VoiceMessageValidationError):
            parse_voice_message({"type": "end", "unexpected": True})

    def test_ready_message_contains_approved_optional_metadata(self) -> None:
        message = ready_message()
        self.assertEqual(message["type"], "ready")
        self.assertEqual(message["protocolVersion"], 1)
        self.assertEqual(message["inputAudio"]["sampleRate"], 16000)
        self.assertEqual(message["outputAudio"]["sampleRate"], 24000)

    def test_audio_message_limit_and_alignment(self) -> None:
        limits = runtime_limits(max_audio_bytes=4)
        self.assertEqual(
            _decode_audio(base64.b64encode(b"\x00\x00").decode(), limits),
            b"\x00\x00",
        )

        with self.assertRaises(VoiceConnectionError) as oversized:
            _decode_audio(base64.b64encode(b"123456").decode(), limits)
        self.assertEqual(oversized.exception.code, "message_too_large")

        with self.assertRaises(VoiceConnectionError) as unaligned:
            _decode_audio(base64.b64encode(b"1").decode(), limits)
        self.assertEqual(unaligned.exception.code, "invalid_message")


class VoiceConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_gemini_receiver_continues_across_multiple_turns(self) -> None:
        first_turn = types.LiveServerMessage.model_validate(
            {
                "server_content": {
                    "input_transcription": {"text": "first"},
                    "turn_complete": True,
                }
            }
        )
        second_turn = types.LiveServerMessage.model_validate(
            {
                "server_content": {
                    "output_transcription": {"text": "second"},
                    "turn_complete": True,
                }
            }
        )
        session = MultiTurnGeminiSession(
            [[first_turn], [second_turn], []]
        )
        output_queue = asyncio.Queue(maxsize=10)

        await _receive_from_gemini(
            session,
            output_queue,
            _ActivityTracker(),
            FakeToolCoordinator(),
        )

        messages = []
        while not output_queue.empty():
            messages.append(output_queue.get_nowait())

        self.assertEqual(session.receive_calls, 3)
        self.assertEqual(
            [message["type"] for message in messages],
            [
                "input_transcription",
                "turn_complete",
                "output_transcription",
                "turn_complete",
            ],
        )

    async def test_disconnect_propagates_and_cleans_up_tasks(self) -> None:
        websocket = DisconnectingWebSocket()

        with self.assertRaises(WebSocketDisconnect):
            await run_voice_connection(
                websocket=websocket,
                session=HangingGeminiSession(),
                product_id=uuid4(),
                limits=runtime_limits(),
            )

        self.assertEqual(websocket.sent[0]["type"], "ready")
        active_voice_tasks = [
            task
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task()
            and task.get_name().startswith("voice-")
            and not task.done()
        ]
        self.assertEqual(active_voice_tasks, [])

    async def test_idle_timeout_is_enforced(self) -> None:
        websocket = HangingWebSocket()

        with self.assertRaises(VoiceConnectionError) as raised:
            await run_voice_connection(
                websocket=websocket,
                session=HangingGeminiSession(),
                product_id=uuid4(),
                limits=runtime_limits(
                    idle_timeout_seconds=0.02,
                    max_duration_seconds=1,
                ),
            )

        self.assertEqual(raised.exception.code, "session_idle_timeout")

    async def test_maximum_duration_is_enforced(self) -> None:
        websocket = HangingWebSocket()

        with self.assertRaises(VoiceConnectionError) as raised:
            await run_voice_connection(
                websocket=websocket,
                session=HangingGeminiSession(),
                product_id=uuid4(),
                limits=runtime_limits(
                    idle_timeout_seconds=1,
                    max_duration_seconds=0.02,
                ),
            )

        self.assertEqual(raised.exception.code, "session_max_duration")

    async def test_tool_call_cancellation_prevents_response(self) -> None:
        session = RecordingToolSession()
        coordinator = GeminiToolCoordinator(
            session=session,
            product_id=uuid4(),
            send_lock=asyncio.Lock(),
            timeout_seconds=1,
        )
        call = types.FunctionCall(
            id="call-1",
            name="search_school_knowledge",
            args={"question": "fees"},
        )

        async def wait_forever(*args, **kwargs):
            await asyncio.Event().wait()

        with patch(
            "app.services.voice_connection_service.execute_gemini_function_call",
            new=AsyncMock(side_effect=wait_forever),
        ):
            coordinator.start(types.LiveServerToolCall(function_calls=[call]))
            await asyncio.sleep(0)
            coordinator.cancel(["call-1"])
            await coordinator.close()

        self.assertEqual(session.responses, [])


if __name__ == "__main__":
    unittest.main()
