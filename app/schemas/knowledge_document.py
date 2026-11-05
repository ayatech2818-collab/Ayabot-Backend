from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class KnowledgeDocumentResponse(BaseModel):
    id: UUID
    product_id: UUID
    title: str
    file_name: str
    file_path: str
    mime_type: str
    file_size: int
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)