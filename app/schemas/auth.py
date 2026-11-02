
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class AuthenticatedUser(BaseModel):
    """Identity verified by Supabase Auth."""

    id: UUID
    email: EmailStr | None = None


class AdminResponse(BaseModel):
    """AYABOT admin profile returned to the frontend."""

    id: UUID
    auth_user_id: UUID
    display_name: str | None = None
    role: Literal["super_admin", "admin"] 
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CurrentAdminResponse(BaseModel):
    """Verified identity plus AYABOT admin permissions."""

    user: AuthenticatedUser
    admin: AdminResponse
