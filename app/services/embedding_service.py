from functools import lru_cache

from google import genai
from google.genai import types

from app.core.config import get_settings


MODEL_NAME = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768


@lru_cache(maxsize=1)
def get_gemini_client():
    settings = get_settings()

    return genai.Client(
        api_key=settings.gemini_api_key
    )


def generate_embedding(text: str) -> list[float]:
    if not text.strip():
        raise ValueError("Cannot generate embedding for empty text")

    response = get_gemini_client().models.embed_content(
        model=MODEL_NAME,
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=EMBEDDING_DIMENSIONS,
        ),
    )

    embedding = response.embeddings[0].values

    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Expected {EMBEDDING_DIMENSIONS} dimensions, "
            f"received {len(embedding)}"
        )

    return embedding