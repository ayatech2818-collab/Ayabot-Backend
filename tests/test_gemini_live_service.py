import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from google.genai import types

from app.services.gemini_live_service import (
    connect_gemini_live,
    execute_gemini_function_call,
)


class FakeLiveConnection:
    def __init__(self, session) -> None:
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        pass


class RecordingLive:
    def __init__(self) -> None:
        self.calls = []
        self.session = object()

    def connect(self, **kwargs):
        self.calls.append(kwargs)
        return FakeLiveConnection(self.session)


class GeminiLiveServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_connection_explicitly_requests_transcriptions(self) -> None:
        live = RecordingLive()
        fake_client = SimpleNamespace(
            aio=SimpleNamespace(live=live),
        )
        voice_config = {
            "config_version": 2,
            "gemini_model": "test-live-model",
            "system_instruction": "Be helpful.",
            "voice_name": "Aoede",
            "response_modalities": ["AUDIO"],
            "audio_settings": {},
        }

        with (
            patch(
                "app.services.gemini_live_service._load_global_voice_config",
                return_value=voice_config,
            ),
            patch(
                "app.services.gemini_live_service.gemini_client",
                fake_client,
            ),
        ):
            async with connect_gemini_live() as session:
                self.assertIs(session, live.session)

        config = live.calls[0]["config"]
        self.assertEqual(live.calls[0]["model"], "test-live-model")
        self.assertEqual(config["input_audio_transcription"], {})
        self.assertEqual(config["output_audio_transcription"], {})

        # Validate against the installed google-genai model, not only our dict.
        validated = types.LiveConnectConfig.model_validate(config)
        self.assertIsNotNone(validated.input_audio_transcription)
        self.assertIsNotNone(validated.output_audio_transcription)

    async def test_tool_search_preserves_authenticated_product_id(self) -> None:
        product_id = uuid4()
        call = types.FunctionCall(
            id="search-1",
            name="search_school_knowledge",
            args={"question": "What are the fees?"},
        )

        with patch(
            "app.services.gemini_live_service._run_knowledge_search",
            return_value={"found": True, "results": []},
        ) as search:
            response = await execute_gemini_function_call(
                call,
                product_id,
                timeout_seconds=1,
            )

        search.assert_called_once_with(product_id, "What are the fees?")
        self.assertTrue(response.response["found"])

    async def test_tool_timeout_returns_bounded_failure(self) -> None:
        call = types.FunctionCall(
            id="search-2",
            name="search_school_knowledge",
            args={"question": "What are the fees?"},
        )

        def slow_search(*args, **kwargs):
            time.sleep(0.05)
            return {"found": True, "results": []}

        with patch(
            "app.services.gemini_live_service._run_knowledge_search",
            side_effect=slow_search,
        ):
            started = time.monotonic()
            response = await execute_gemini_function_call(
                call,
                uuid4(),
                timeout_seconds=0.01,
            )
            elapsed = time.monotonic() - started

        self.assertLess(elapsed, 0.05)
        self.assertFalse(response.response["found"])
        self.assertIn("timed out", response.response["message"].lower())

    async def test_unknown_tool_returns_explicit_error(self) -> None:
        call = types.FunctionCall(
            id="unknown-1",
            name="unknown_tool",
            args={},
        )
        response = await execute_gemini_function_call(
            call,
            uuid4(),
            timeout_seconds=1,
        )
        self.assertIn("Unknown function", response.response["error"])


if __name__ == "__main__":
    unittest.main()
