from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ServiceCreate(BaseModel):
    system_id: UUID
    name: str
    description: str | None = None
    base_url: str
    docker_container_name: str | None = None


class ServiceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    base_url: str | None = None
    docker_container_name: str | None = None


class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    system_id: UUID
    name: str
    description: str | None
    base_url: str
    docker_container_name: str | None
    created_at: datetime
    updated_at: datetime