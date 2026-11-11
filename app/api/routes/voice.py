
import asyncio
import base64
import binascii
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from google.genai import types
from sqlalchemy.orm import Session

from app.api.dependencies import ProductAuthContext, get_current_product
from app.db.dependencies import get_db
from app.db.session import SessionLocal
from app.services.voice_session_service import (
    create_voice_session_ticket,
    consume_voice_session_ticket,
)
from app.services.gemini_live_service import (
    connect_gemini_live,
    handle_gemini_tool_call,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/voice",
    tags=["Voice"],
)


@router.post(
    "/session",
    status_code=status.HTTP_201_CREATED,
)
def create_voice_session(
    ctx: Annotated[
        ProductAuthContext,
        Depends(get_current_product),
    ],
    db: Annotated[Session, Depends(get_db)],
):
    return create_voice_session_ticket(
        db=db,
        product_id=ctx.product.id,
        credential_id=ctx.credential.id,
    )


def validate_voice_ticket(raw_ticket: str):
    db = SessionLocal()

    try:
        return consume_voice_session_ticket(
            db=db,
            raw_ticket=raw_ticket,
        )
    finally:
        db.close()


@router.websocket("/ws")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()

    try:
        auth_message = await asyncio.wait_for(
            websocket.receive_json(),
            timeout=10,
        )

        if auth_message.get("type") != "auth":
            await websocket.close(
                code=1008,
                reason="Authentication required",
            )
            return

        raw_ticket = auth_message.get("ticket")

        if not isinstance(raw_ticket, str) or not raw_ticket:
            await websocket.close(
                code=1008,
                reason="Invalid ticket",
            )
            return

        try:
            ticket = await asyncio.to_thread(
                validate_voice_ticket,
                raw_ticket,
            )
        except Exception:
            logger.warning("Voice ticket validation failed")
            await websocket.close(
                code=1008,
                reason="Invalid or expired ticket",
            )
            return

        product_id: UUID = ticket.product_id

        await websocket.send_json({"type": "connecting"})

        async with connect_gemini_live() as session:
            await websocket.send_json({"type": "ready"})

            async def receive_from_browser():
                while True:
                    message = await websocket.receive_json()
                    message_type = message.get("type")

                    if message_type == "audio":
                        encoded_audio = message.get("data")

                        if not isinstance(encoded_audio, str):
                            continue

                        try:
                            audio_bytes = base64.b64decode(
                                encoded_audio,
                                validate=True,
                            )
                        except (ValueError, binascii.Error):
                            continue

                        await session.send_realtime_input(
                            audio=types.Blob(
                                data=audio_bytes,
                                mime_type="audio/pcm;rate=16000",
                            )
                        )

                    elif message_type == "text":
                        text = message.get("text", "")

                        if isinstance(text, str) and text.strip():
                            await session.send_client_content(
                                turns=types.Content(
                                    role="user",
                                    parts=[types.Part(text=text)],
                                ),
                                turn_complete=True,
                            )

                    elif message_type == "end":
                        return

            async def receive_from_gemini():
                async for response in session.receive():

                    if response.tool_call:
                        await handle_gemini_tool_call(
                            session=session,
                            tool_call=response.tool_call,
                            product_id=product_id,
                        )
                        continue

                    server_content = response.server_content

                    if not server_content:
                        continue

                    if server_content.input_transcription:
                        await websocket.send_json({
                            "type": "input_transcription",
                            "text": server_content.input_transcription.text,
                        })

                    if server_content.output_transcription:
                        await websocket.send_json({
                            "type": "output_transcription",
                            "text": server_content.output_transcription.text,
                        })

                    if server_content.model_turn:
                        for part in server_content.model_turn.parts:
                            if part.inline_data and part.inline_data.data:
                                audio_data = base64.b64encode(
                                    part.inline_data.data
                                ).decode("ascii")

                                await websocket.send_json({
                                    "type": "audio",
                                    "data": audio_data,
                                    "mimeType": "audio/pcm;rate=24000",
                                })

                    if server_content.interrupted:
                        await websocket.send_json({
                            "type": "interrupted",
                        })

                    if server_content.turn_complete:
                        await websocket.send_json({
                            "type": "turn_complete",
                        })

            browser_task = asyncio.create_task(receive_from_browser())
            gemini_task = asyncio.create_task(receive_from_gemini())

            try:
                done, pending = await asyncio.wait(
                    [browser_task, gemini_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in done:
                    exception = task.exception()
                    if exception:
                        raise exception

            finally:
                for task in (browser_task, gemini_task):
                    if not task.done():
                        task.cancel()

                await asyncio.gather(
                    browser_task,
                    gemini_task,
                    return_exceptions=True,
                )

    except WebSocketDisconnect:
        logger.info("Voice client disconnected")

    except asyncio.TimeoutError:
        logger.warning("Voice authentication timed out")
        try:
            await websocket.close(
                code=1008,
                reason="Authentication timeout",
            )
        except Exception:
            pass

    except Exception:
        logger.exception("Voice WebSocket error")
        try:
            await websocket.send_json({
                "type": "error",
                "message": "Voice connection encountered an error.",
            })
            await websocket.close(code=1011)
        except Exception:
            pass
