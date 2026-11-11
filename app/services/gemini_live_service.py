
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from google import genai

from app.core.config import get_settings

from app.core.prompts import AYABOT_SYSTEM_INSTRUCTION

import asyncio

from app.db.session import SessionLocal
from google.genai import types

from uuid import UUID

from sqlalchemy.orm import Session

from app.services.knowledge_search_service import search_knowledge

settings = get_settings()

MODEL_NAME = "gemini-2.5-flash-native-audio-preview-09-2025"

gemini_client = genai.Client(
    api_key=settings.gemini_api_key,
)


@asynccontextmanager
async def connect_gemini_live() -> AsyncIterator:
    """
    Open a Gemini Live session and manage its lifecycle.
    """

    
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
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "question": {
                            "type": "STRING",
                            "description": "The school-related question to search for."
                        }
                    },
                    "required": ["question"],
                },
            }
        ]
    }


    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": AYABOT_SYSTEM_INSTRUCTION,
        "speech_config": {
            "voice_config": {
                "prebuilt_voice_config": {
                    "voice_name": "Aoede",
                }
            }
        },
        "tools": [knowledge_tool],
    }

    async with gemini_client.aio.live.connect(
        model=MODEL_NAME,
        config=config,
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
            "message": "No relevant information was found in the school knowledge base.",
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


async def handle_gemini_tool_call(
    session,
    tool_call,
    product_id: UUID,
) -> None:
    """Execute Gemini function calls and return their results."""

    function_responses = []

    for function_call in tool_call.function_calls:
        if function_call.name == "search_school_knowledge":
            question = (function_call.args or {}).get("question", "")

            if not question.strip():
                result = {
                    "found": False,
                    "message": "A valid question was not provided.",
                    "results": [],
                }
            else:
                try:
                    result = await asyncio.to_thread(
                        _run_knowledge_search,
                        product_id,
                        question,
                    )
                except Exception:
                    result = {
                        "found": False,
                        "message": "Knowledge search is temporarily unavailable.",
                        "results": [],
                    }
        else:
            result = {
                "error": f"Unknown function: {function_call.name}"
            }

        function_responses.append(
            types.FunctionResponse(
                id=function_call.id,
                name=function_call.name,
                response=result,
            )
        )

    await session.send_tool_response(
        function_responses=function_responses
    )
