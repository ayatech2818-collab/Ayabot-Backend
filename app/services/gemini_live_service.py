
import asyncio
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from uuid import UUID

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AyabotVoiceConfig
from app.services.knowledge_search_service import search_knowledge


settings = get_settings()
logger = logging.getLogger(__name__)

gemini_client = genai.Client(
    api_key=settings.gemini_api_key,
)


def _load_global_voice_config() -> dict:
    """
    Load a snapshot of the global voice configuration.

    Each new Gemini session receives its own configuration snapshot.
    """

    db = SessionLocal()

    try:
        voice_config = (
            db.query(AyabotVoiceConfig)
            .filter(AyabotVoiceConfig.config_key == "global")
            .one_or_none()
        )

        if voice_config is None:
            raise RuntimeError(
                "Global AYABOT voice configuration does not exist."
            )

        if not voice_config.is_enabled:
            raise RuntimeError(
                "AYABOT voice service is currently disabled."
            )

        modalities_config = voice_config.response_modalities or {}
        modalities = modalities_config.get("modalities")

        if not isinstance(modalities, list) or not modalities:
            raise RuntimeError(
                "Invalid response_modalities in global voice configuration."
            )

        if not voice_config.gemini_model.strip():
            raise RuntimeError("Gemini model is not configured.")

        if not voice_config.system_instruction.strip():
            raise RuntimeError("System instruction is empty.")

        if not voice_config.voice_name.strip():
            raise RuntimeError("Voice name is not configured.")

        return {
            "config_version": voice_config.config_version,
            "gemini_model": voice_config.gemini_model,
            "system_instruction": voice_config.system_instruction,
            "voice_name": voice_config.voice_name,
            "response_modalities": modalities.copy(),
            "audio_settings": dict(voice_config.audio_settings or {}),
        }

    finally:
        db.close()


@asynccontextmanager
async def connect_gemini_live() -> AsyncIterator:
    """
    Open a Gemini Live session using the latest global configuration.

    Configuration is loaded once per session. Changes made by an admin
    will apply to new sessions, not sessions that are already running.
    """

    voice_config = await asyncio.to_thread(
        _load_global_voice_config
    )

    knowledge_tool = {
        "function_declarations": [
            {
                "name": "search_school_knowledge",
                "description": (
                    "Search Ayadi Glocal School's verified knowledge base "
                    "for information about curriculum, fees, admissions, "
                    "subjects, class schedules, policies, and school activities. "
                    "Use this whenever a parent asks for factual school information."
                ),
                "behavior": "BLOCKING",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "question": {
                            "type": "STRING",
                            "description": (
                                "The school-related question to search for."
                            ),
                        }
                    },
                    "required": ["question"],
                },
            }
        ]
    }

    gemini_config = {
        "response_modalities": voice_config["response_modalities"],
        "system_instruction": voice_config["system_instruction"],
        "speech_config": {
            "voice_config": {
                "prebuilt_voice_config": {
                    "voice_name": voice_config["voice_name"],
                }
            }
        },
        "tools": [knowledge_tool],
        "input_audio_transcription": {},
        "output_audio_transcription": {},
    }

    async with gemini_client.aio.live.connect(
        model=voice_config["gemini_model"],
        config=gemini_config,
    ) as session:
        yield session


def execute_knowledge_search(
    db: Session,
    product_id: UUID,
    question: str,
) -> dict:
    """
    Search verified school knowledge for the authenticated product.
    """

    results = search_knowledge(
        db=db,
        question=question,
        product_id=product_id,
        limit=5,
        min_similarity=0.50,
    )

    if not results:
        return {
            "found": False,
            "message": (
                "No relevant information was found in the school knowledge base."
            ),
            "results": [],
        }

    return {
        "found": True,
        "results": [
            {
                "content": item["content"],
                "similarity": round(float(item["similarity"]), 3),
            }
            for item in results
        ],
    }


def _run_knowledge_search(
    product_id: UUID,
    question: str,
) -> dict:
    """Run synchronous database search with its own session."""

    db = SessionLocal()

    try:
        return execute_knowledge_search(
            db=db,
            product_id=product_id,
            question=question,
        )
    finally:
        db.close()


async def execute_gemini_function_call(
    function_call,
    product_id: UUID,
    *,
    timeout_seconds: float,
) -> types.FunctionResponse:
    """Execute one Gemini function call within a bounded wait time."""

    if function_call.name != "search_school_knowledge":
        result = {
            "error": f"Unknown function: {function_call.name}",
        }
    else:
        question = (function_call.args or {}).get("question", "")

        if not isinstance(question, str) or not question.strip():
            result = {
                "found": False,
                "message": "A valid question was not provided.",
                "results": [],
            }
        else:
            try:
                async with asyncio.timeout(timeout_seconds):
                    result = await asyncio.to_thread(
                        _run_knowledge_search,
                        product_id,
                        question,
                    )
            except TimeoutError:
                logger.warning(
                    "Gemini knowledge tool timed out: product_id=%s",
                    product_id,
                )
                result = {
                    "found": False,
                    "message": "Knowledge search timed out.",
                    "results": [],
                }
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Gemini knowledge tool failed: product_id=%s",
                    product_id,
                )
                result = {
                    "found": False,
                    "message": (
                        "Knowledge search is temporarily unavailable."
                    ),
                    "results": [],
                }

    return types.FunctionResponse(
        id=function_call.id,
        name=function_call.name,
        response=result,
    )


async def handle_gemini_tool_call(
    session,
    tool_call,
    product_id: UUID,
) -> None:
    """Backward-compatible helper for callers that do not need cancellation."""

    function_responses = [
        await execute_gemini_function_call(
            function_call,
            product_id,
            timeout_seconds=settings.voice_tool_timeout_seconds,
        )
        for function_call in tool_call.function_calls
    ]

    await session.send_tool_response(
        function_responses=function_responses,
    )
