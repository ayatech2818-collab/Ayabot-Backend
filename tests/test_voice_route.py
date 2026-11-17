import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.api.routes.voice import voice_websocket
from app.services.voice_connection_service import VoiceConnectionError


class RouteWebSocket:
    def __init__(self, incoming) -> None:
        self.incoming = list(incoming)
        self.accepted = False
        self.sent = []
        self.closed = []

    async def accept(self) -> None:
        self.accepted = True

    async def receive_json(self):
        if self.incoming:
            return self.incoming.pop(0)
        raise AssertionError("Unexpected receive")

    async def send_json(self, message) -> None:
        self.sent.append(message)

    async def close(self, *, code=1000, reason=None) -> None:
        self.closed.append((code, reason))


class RouteGeminiSession:
    async def send_realtime_input(self, **kwargs) -> None:
        pass

    async def send_client_content(self, **kwargs) -> None:
        pass

    async def send_tool_response(self, **kwargs) -> None:
        pass

    def receive(self):
        async def iterator():
            # The browser's end message should finish the session first.
            import asyncio

            await asyncio.Event().wait()
            if False:
                yield None

        return iterator()


@asynccontextmanager
async def fake_gemini_connection():
    yield RouteGeminiSession()


class VoiceRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_route_preserves_auth_connecting_ready_end_flow(self) -> None:
        websocket = RouteWebSocket(
            [
                {"type": "auth", "ticket": "valid-ticket"},
                {"type": "end"},
            ]
        )
        product_id = uuid4()
        ticket = SimpleNamespace(product_id=product_id)

        with (
            patch(
                "app.api.routes.voice.validate_voice_ticket",
                return_value=ticket,
            ) as validate,
            patch(
                "app.api.routes.voice.connect_gemini_live",
                side_effect=fake_gemini_connection,
            ),
        ):
            await voice_websocket(websocket)

        self.assertTrue(websocket.accepted)
        validate.assert_called_once_with("valid-ticket")
        self.assertEqual(
            [message["type"] for message in websocket.sent],
            ["connecting", "ready"],
        )
        self.assertEqual(websocket.closed, [])

    async def test_invalid_ticket_closes_with_existing_policy_code(self) -> None:
        websocket = RouteWebSocket(
            [{"type": "auth", "ticket": "replayed-ticket"}]
        )

        with patch(
            "app.api.routes.voice.validate_voice_ticket",
            side_effect=RuntimeError("already consumed"),
        ):
            await voice_websocket(websocket)

        self.assertTrue(websocket.accepted)
        self.assertEqual(websocket.sent, [])
        self.assertEqual(websocket.closed[0][0], 1008)

    async def test_non_auth_first_message_is_rejected(self) -> None:
        websocket = RouteWebSocket([{"type": "end"}])
        await voice_websocket(websocket)
        self.assertEqual(websocket.closed[0][0], 1008)
        self.assertEqual(websocket.closed[0][1], "Authentication required")

    async def test_runtime_error_uses_approved_error_metadata(self) -> None:
        websocket = RouteWebSocket(
            [{"type": "auth", "ticket": "valid-ticket"}]
        )
        ticket = SimpleNamespace(product_id=uuid4())
        session_error = VoiceConnectionError(
            code="session_idle_timeout",
            message="Voice session ended after a period of inactivity.",
            recoverable=True,
            close_code=1000,
        )

        with (
            patch(
                "app.api.routes.voice.validate_voice_ticket",
                return_value=ticket,
            ),
            patch(
                "app.api.routes.voice.connect_gemini_live",
                side_effect=fake_gemini_connection,
            ),
            patch(
                "app.api.routes.voice.run_voice_connection",
                new=AsyncMock(side_effect=session_error),
            ),
        ):
            await voice_websocket(websocket)

        self.assertEqual(websocket.sent[0], {"type": "connecting"})
        self.assertEqual(websocket.sent[1]["type"], "error")
        self.assertEqual(
            websocket.sent[1]["code"],
            "session_idle_timeout",
        )
        self.assertTrue(websocket.sent[1]["recoverable"])
        self.assertEqual(websocket.closed[0][0], 1000)


if __name__ == "__main__":
    unittest.main()
