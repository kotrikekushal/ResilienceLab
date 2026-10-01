from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ResultCreate(BaseModel):
    execution_id: UUID
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    error_rate: float
    average_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    throughput: float
    availability: float


class ResultUpdate(BaseModel):
    total_requests: int | None = None
    successful_requests: int | None = None
    failed_requests: int | None = None
    success_rate: float | None = None
    error_rate: float | None = None
    average_latency_ms: float | None = None
    p50_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    p99_latency_ms: float | None = None
    throughput: float | None = None
    availability: float | None = None


class ResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    execution_id: UUID
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    error_rate: float
    average_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    throughput: float
    availability: float
    created_at: datetime