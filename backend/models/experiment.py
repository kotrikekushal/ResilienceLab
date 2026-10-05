from datetime import datetime
from uuid import UUID
from typing import Any
from pydantic import BaseModel, ConfigDict
from backend.models.experiment_run import ServiceResultResponse
from backend.models.result import ResultResponse
from typing import Any

class ExperimentCreate(BaseModel):
    system_id: UUID
    name: str
    description: str | None = None
    hypothesis: dict[str, Any] | None = None


class ExperimentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None  = None
    hypothesis: dict[str, Any] | None = None


class ExperimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    system_id: UUID
    name: str
    description: str | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    created_at: datetime
    result: ResultResponse | None = None
    hypothesis: dict[str, Any] | None = None

class ExecutionResponse(BaseModel):
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
    result: ResultResponse | None
    services: list[ServiceResultResponse]

class ExperimentRunResponse(BaseModel):
    experiment_id: UUID
    status: str
    executions: list[ExecutionResponse]

class ExperimentCloneRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class ExperimentReuseRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    workload_overrides: dict[str, Any] | None = None
    failure_overrides: list[dict[str, Any]] | None = None

class ConfigurationServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    base_url: str
    docker_container_name: str | None


class ConfigurationDependencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_service_id: UUID
    target_service_id: UUID
    dependency_type: str


class ConfigurationSystemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    services: list[ConfigurationServiceResponse]
    dependencies: list[ConfigurationDependencyResponse]


class ConfigurationWorkloadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    total_requests: int
    requests_per_second: int
    duration_seconds: int


class ConfigurationFailureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    service_id: UUID
    failure_type: str
    duration_seconds: int | None
    parameters: dict | None


class ExperimentConfigurationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    system_id: UUID
    name: str
    description: str | None
    status: str

    system: ConfigurationSystemResponse
    workload: ConfigurationWorkloadResponse | None
    failures: list[ConfigurationFailureResponse]