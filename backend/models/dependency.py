from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DependencyCreate(BaseModel):
    source_service_id: UUID
    target_service_id: UUID
    dependency_type: str


class DependencyUpdate(BaseModel):
    dependency_type: str | None = None


class DependencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_service_id: UUID
    target_service_id: UUID
    dependency_type: str
    created_at: datetime