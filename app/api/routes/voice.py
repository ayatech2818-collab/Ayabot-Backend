
import asyncio
import logging
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies import ProductAuthContext, get_current_product
from app.db.dependencies import get_db
from app.db.session import SessionLocal
from app.models import AyabotVoiceConfig
from app.core.config import get_settings
from app.schemas.voice import (
    VoiceAuthMessage,
    VoiceMessageValidationError,
    error_message,
    parse_voice_message,
)
from app.services.voice_connection_service import (
    VoiceConnectionError,
    run_voice_connection,
)
from app.services.voice_session_service import (
    create_voice_session_ticket,
    consume_voice_session_ticket,
)
from app.services.gemini_live_service import (
    connect_gemini_live,
)

logger = logging.getLogger(__name__)
settings = get_settings()

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
    voice_config = (
        db.query(AyabotVoiceConfig)
        .filter(AyabotVoiceConfig.config_key == "global")
        .one_or_none()
    )

    if voice_config is None or not voice_config.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AYABOT voice service is currently unavailable.",
        )

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


async def close_voice_websocket(
    websocket: WebSocket,
    error: VoiceConnectionError,
) -> None:
    try:
        await websocket.send_json(
            error_message(
                error.message,
                code=error.code,
                recoverable=error.recoverable,
            )
        )
        await websocket.close(
            code=error.close_code,
            reason=error.message,
        )
    except Exception:
        pass


@router.websocket("/ws")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()

    try:
        # Step 1: Authenticate the WebSocket connection.
        try:
            auth_message = parse_voice_message(
                await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=settings.voice_auth_timeout_seconds,
                )
            )
        except VoiceMessageValidationError:
            await websocket.close(
                code=1008,
                reason="Invalid authentication message",
            )
            return

        if not isinstance(auth_message, VoiceAuthMessage):
            await websocket.close(
                code=1008,
                reason="Authentication required",
            )
            return

        raw_ticket = auth_message.ticket

        if (
            not raw_ticket
            or len(raw_ticket) > settings.voice_max_ticket_chars
        ):
            await websocket.close(code=1008, reason="Invalid ticket")
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

        await websocket.send_json({
            "type": "connecting",
        })

        # Step 2: Establish the Gemini Live session.
        async with connect_gemini_live() as session:
            await run_voice_connection(
                websocket=websocket,
                session=session,
                product_id=product_id,
            )

        logger.info(
            "Voice session ended by client: product_id=%s",
            product_id,
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

    except VoiceConnectionError as exc:
        logger.info(
            "Voice connection ended: code=%s recoverable=%s",
            exc.code,
            exc.recoverable,
        )
        await close_voice_websocket(websocket, exc)

    except Exception:
        logger.exception("Voice WebSocket error")

        try:
            await close_voice_websocket(
                websocket,
                VoiceConnectionError(
                    code="internal_error",
                    message="Voice connection encountered an error.",
                    recoverable=True,
                    close_code=1011,
                ),
            )
        except Exception:
            pass
