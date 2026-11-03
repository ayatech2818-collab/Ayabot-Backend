from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CredentialCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    expires_at: datetime | None = None


class CredentialResponse(BaseModel):
    id: UUID
    product_id: UUID
    name: str
    key_prefix: str
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    revoked_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class CredentialCreatedResponse(CredentialResponse):
    api_key: str