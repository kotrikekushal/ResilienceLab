from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SystemCreate(BaseModel):
    name: str
    description: str | None = None


class SystemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class SystemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    