
import httpx

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies import get_current_admin
from app.core.config import get_settings
from app.models.admin import AyabotAdmin
from app.schemas.auth import CurrentAdminResponse
from app.services.auth_service import build_current_admin_response


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/token")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    settings = get_settings()

    url = (
        f"{settings.supabase_url.rstrip('/')}"
        "/auth/v1/token?grant_type=password"
    )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                url,
                headers={
                    "apikey": settings.supabase_auth_key,
                    "Content-Type": "application/json",
                },
                json={
                    "email": form_data.username,
                    "password": form_data.password,
                },
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        data = response.json()

        return {
            "access_token": data["access_token"],
            "token_type": "bearer",
        }

    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to Supabase Auth",
        ) from None


@router.get("/me", response_model=CurrentAdminResponse)
def get_me(
    admin: Annotated[AyabotAdmin, Depends(get_current_admin)],
) -> CurrentAdminResponse:
    return build_current_admin_response(admin, email=None)
