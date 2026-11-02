
from app.models.admin import AyabotAdmin
from app.schemas.auth import AdminResponse, AuthenticatedUser, CurrentAdminResponse


def build_current_admin_response(
    admin: AyabotAdmin,
    email: str | None,
) -> CurrentAdminResponse:
    return CurrentAdminResponse(
        user=AuthenticatedUser(
            id=admin.auth_user_id,
            email=email,
        ),
        admin=AdminResponse.model_validate(admin),
    )
