from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MetricCreate(BaseModel):
    execution_id: UUID
    service_id: UUID
    timestamp: datetime
    latency_ms: float | None = None
    status_code: int | None = None
    success: bool | None = None
    cpu_usage_percent: float | None = None
    memory_usage_mb: float | None = None
    request_count: int = 0
    error_count: int = 0


class MetricUpdate(BaseModel):
    timestamp: datetime | None = None
    latency_ms: float | None = None
    status_code: int | None = None
    success: bool | None = None
    cpu_usage_percent: float | None = None
    memory_usage_mb: float | None = None
    request_count: int | None = None
    error_count: int | None = None


class MetricResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    execution_id: UUID
    service_id: UUID
    timestamp: datetime
    latency_ms: float | None
    status_code: int | None
    success: bool | None
    cpu_usage_percent: float | None
    memory_usage_mb: float | None
    request_count: int
    error_count: int