
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_admin
from app.db.dependencies import get_db
from app.models.admin import AyabotAdmin
from app.schemas.auth import CurrentAdminResponse
from app.services.auth_service import build_current_admin_response


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/me", response_model=CurrentAdminResponse)
def get_me(
    admin: Annotated[AyabotAdmin, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> CurrentAdminResponse:
    # The verified token identifies the admin.
    # Fetch the user's email separately only if needed.
    # For now, return the verified admin profile.
    return build_current_admin_response(admin, email=None)
