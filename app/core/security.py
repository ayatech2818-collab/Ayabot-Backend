
from functools import lru_cache

import jwt
from jwt import PyJWKClient

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_jwks_client() -> PyJWKClient:
    settings = get_settings()

    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL is not configured")

    jwks_url = (
        f"{settings.supabase_url.rstrip('/')}"
        "/auth/v1/.well-known/jwks.json"
    )

    return PyJWKClient(
        jwks_url,
        cache_jwk_set=True,
        lifespan=3600,
    )


def verify_supabase_access_token(token: str) -> dict:
    settings = get_settings()

    signing_key = get_jwks_client().get_signing_key_from_jwt(token)

    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["ES256"],
        audience="authenticated",
        issuer=f"{settings.supabase_url.rstrip('/')}/auth/v1",
        options={
            "require": ["exp", "sub", "iss", "aud"],
        },
    )
