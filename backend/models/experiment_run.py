from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from backend.models.metric import MetricResponse
from backend.models.result import ResultResponse


class RunSystem(BaseModel):
    name: str
    description: str | None = None


class RunService(BaseModel):
    name: str
    description: str | None = None
    base_url: str
    docker_container_name: str | None = None


class RunDependency(BaseModel):
    source_service: str
    target_service: str
    dependency_type: str


class RunExperiment(BaseModel):
    name: str
    description: str | None = None


class RunWorkload(BaseModel):
    total_requests: int
    requests_per_second: int
    duration_seconds: int


class RunFailure(BaseModel):
    service: str
    failure_type: str
    duration_seconds: int | None = None
    parameters: dict | None = None


class ExperimentRunCreate(BaseModel):
    system: RunSystem
    services: list[RunService]
    dependencies: list[RunDependency]
    experiment: RunExperiment
    workload: RunWorkload
    failures: list[RunFailure]


class ServiceResultResponse(BaseModel):
    service_id: UUID
    service_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_latency_ms: float


class ExecutionResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    experiment_id: UUID
    run_number: int
    run_type: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    created_at: datetime
    result: ResultResponse | None
    services: list[ServiceResultResponse]


class OverallAnalysisResponse(BaseModel):
    resilience_score: float
    severity: str
    summary: str
    failure_resistance_score: float
    recovery_score: float


class DegradationAnalysisResponse(BaseModel):
    success_rate_drop_percentage_points: float
    error_rate_increase_percentage_points: float
    latency_increase_percentage: float
    throughput_decrease_percentage: float
    availability_drop_percentage_points: float


class RecoveryAnalysisResponse(BaseModel):
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
    recovery_time_seconds: float | None
    recovered: bool
    success_rate_recovered: bool
    latency_recovered: bool
    throughput_recovered: bool


class FailureResistanceScoreResponse(BaseModel):
    success_score: float
    latency_score: float
    throughput_score: float
    failure_resistance_score: float


class RecoveryScoreResponse(BaseModel):
    success_score: float
    latency_score: float
    throughput_score: float
    recovery_score: float


class ScoreBreakdownResponse(BaseModel):
    failure_resistance: FailureResistanceScoreResponse
    recovery: RecoveryScoreResponse


class ServiceImpactResponse(BaseModel):
    service_id: UUID
    service_name: str
    baseline_success_rate: float
    failure_success_rate: float
    recovery_success_rate: float
    baseline_latency_ms: float
    failure_latency_ms: float
    recovery_latency_ms: float
    success_rate_drop_percentage_points: float
    latency_increase_percentage: float
    recovered: bool
    impact: str


class FailureImpactResponse(BaseModel):
    failure_id: UUID | None
    service_id: UUID | None
    failure_type: str | None
    duration_seconds: int | None
    parameters: dict | None
    impact: str


class AnalysisResponse(BaseModel):
    experiment_id: UUID
    overall: OverallAnalysisResponse
    baseline: dict
    failure: dict
    degradation: DegradationAnalysisResponse
    recovery: RecoveryAnalysisResponse
    score_breakdown: ScoreBreakdownResponse
    services: list[ServiceImpactResponse]
    failures: list[FailureImpactResponse]
    recommendations: list[str]


class ExperimentRunResponse(BaseModel):
    experiment_id: UUID
    status: str
    executions: list[ExecutionResponse]
    analysis: AnalysisResponse

class ExperimentQueuedResponse(BaseModel):
    experiment_id: UUID
    task_id: str
    status: str

class ExecutionDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    experiment_id: UUID
    run_number: int
    run_type: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    created_at: datetime

    result: ResultResponse | None = None
    metrics: list[MetricResponse] = []

class ExecutionHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    experiment_id: UUID
    run_number: int
    run_type: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    created_at: datetime