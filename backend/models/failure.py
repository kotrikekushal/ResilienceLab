from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class FailureCreate(BaseModel):
    experiment_id: UUID
    service_id: UUID
    failure_type: str
    duration_seconds: int | None = None
    parameters: dict | None = None

    @field_validator("failure_type")
    @classmethod
    def validate_failure_type(cls, value):
        allowed_failure_types = {
            "latency",
            "error",
            "timeout",
            "connection_error",
            "connection_reset",
            "dns_error",
            "service_unavailable",
            "rate_limit",
            "server_error",
            "cpu_stress",
            "memory_stress",
            "network_delay",
            "packet_loss",
            "bandwidth_limit",
            "network_partition",
            "container_crash",
            "disk_stress",
        }

        if value not in allowed_failure_types:
            raise ValueError(
                f"Unsupported failure type: {value}"
            )

        return value

    @field_validator("duration_seconds")
    @classmethod
    def validate_duration(cls, value):
        if value is not None and value <= 0:
            raise ValueError(
                "duration_seconds must be greater than 0"
            )

        return value
    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, value, info):
        if value is None:
            return value

        failure_type = info.data.get("failure_type")

        if failure_type == "cpu_stress":
            cpu_workers = value.get("cpu_workers")

            if cpu_workers is not None and cpu_workers <= 0:
                raise ValueError(
                    "cpu_workers must be greater than 0"
                )

        elif failure_type == "memory_stress":
            memory_mb = value.get("memory_mb")

            if memory_mb is not None and memory_mb <= 0:
                raise ValueError(
                    "memory_mb must be greater than 0"
                )

        elif failure_type == "network_delay":
            delay_ms = value.get("delay_ms")

            if delay_ms is not None and delay_ms <= 0:
                raise ValueError(
                    "delay_ms must be greater than 0"
                )

        elif failure_type == "packet_loss":
            loss_percent = value.get("loss_percent")

            if loss_percent is not None and not 0 <= loss_percent <= 100:
                raise ValueError(
                    "loss_percent must be between 0 and 100"
                )

        elif failure_type == "bandwidth_limit":
            bandwidth_mbps = value.get("bandwidth_mbps")

            if bandwidth_mbps is not None and bandwidth_mbps <= 0:
                raise ValueError(
                    "bandwidth_mbps must be greater than 0"
                )

        elif failure_type == "disk_stress":
            size_mb = value.get("size_mb")

            if size_mb is not None and size_mb <= 0:
                raise ValueError(
                    "size_mb must be greater than 0"
                )

        return value


class FailureUpdate(BaseModel):
    failure_type: str | None = None
    duration_seconds: int | None = None
    parameters: dict | None = None

    @field_validator("failure_type")
    @classmethod
    def validate_failure_type(cls, value):
        allowed_failure_types = {
            "latency",
            "error",
            "timeout",
            "connection_error",
            "connection_reset",
            "dns_error",
            "service_unavailable",
            "rate_limit",
            "server_error",
            "cpu_stress",
            "memory_stress",
            "network_delay",
            "packet_loss",
            "bandwidth_limit",
            "network_partition",
            "container_crash",
            "disk_stress",
        }

        if value not in allowed_failure_types:
            raise ValueError(
                f"Unsupported failure type: {value}"
            )

        return value

    @field_validator("duration_seconds")
    @classmethod
    def validate_duration(cls, value):
        if value is not None and value <= 0:
            raise ValueError(
                "duration_seconds must be greater than 0"
            )

        return value


class FailureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    experiment_id: UUID
    service_id: UUID
    failure_type: str
    duration_seconds: int | None
    parameters: dict | None
    created_at: datetime