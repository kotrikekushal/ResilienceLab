from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict,Field


class WorkloadCreate(BaseModel):
    experiment_id: UUID
    total_requests: int = Field(gt=0)
    requests_per_second: int = Field(gt=0)
    duration_seconds: int = Field(gt=0)


class WorkloadUpdate(BaseModel):
    total_requests: int | None = Field(default=None, gt=0)
    requests_per_second: int | None = Field(default=None, gt=0)
    duration_seconds: int | None = Field(default=None, gt=0)

class WorkloadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    experiment_id: UUID
    total_requests: int
    requests_per_second: int
    duration_seconds: int
    created_at: datetime