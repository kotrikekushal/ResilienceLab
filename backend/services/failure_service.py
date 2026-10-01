import asyncio
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

from backend.db.models.failure import FailureDB
from backend.services.infrastructure_failure_injector import (
    inject_cpu_stress,
    inject_memory_stress,
    inject_network_delay,
    inject_packet_loss,
    inject_bandwidth_limit,
    inject_network_partition,
    inject_container_crash,
    inject_disk_stress,
)


APPLICATION_FAILURE_TYPES = {
    "latency",
    "error",
    "timeout",
    "connection_error",
    "connection_reset",
    "dns_error",
    "service_unavailable",
    "rate_limit",
    "server_error",
}

INFRASTRUCTURE_FAILURE_TYPES = {
    "cpu_stress",
    "memory_stress",
    "network_delay",
    "packet_loss",
    "bandwidth_limit",
    "network_partition",
    "container_crash",
    "disk_stress",
}

DEPENDENCY_FAILURE_TYPE = "dependency_error"


@dataclass
class FailureExecutionContext:
    application_failures: list[tuple[str, str]] = field(
        default_factory=list
    )
    dependency_failures: list[str] = field(
        default_factory=list
    )
    infrastructure_tasks: list[asyncio.Task] = field(
        default_factory=list
    )


async def start_multiple_failures(
    failures: list[FailureDB],
    services: list[Any],
    default_duration_seconds: int,
) -> FailureExecutionContext:

    context = FailureExecutionContext()

    if not failures:
        return context

    services_by_id = {
        service.id: service
        for service in services
    }

    application_proxy_url = os.getenv(
        "APPLICATION_FAILURE_PROXY_URL",
        "http://application-failure-proxy:8002",
    ).rstrip("/")

    dependency_control_url_default = os.getenv(
        "DEPENDENCY_SERVICE_CONTROL_URL",
        "http://dependency-service:8003",
    ).rstrip("/")

    infrastructure_tasks: list[asyncio.Task] = []

    try:

        for failure in failures:

            service = services_by_id.get(
                failure.service_id
            )

            if service is None:
                raise ValueError(
                    f"Failure '{failure.id}' references "
                    f"unknown service '{failure.service_id}'"
                )

            parameters = failure.parameters or {}

            duration_seconds = (
                failure.duration_seconds
                if failure.duration_seconds is not None
                else default_duration_seconds
            )

            # ------------------------------------------------
            # APPLICATION FAILURE
            # ------------------------------------------------

            if failure.failure_type in APPLICATION_FAILURE_TYPES:

                response = await _post_failure(
                    url=(
                        f"{application_proxy_url}"
                        f"/fault/{service.name}"
                    ),
                    payload={
                        "failure_type": failure.failure_type,
                        "duration_seconds": duration_seconds,
                        "parameters": parameters,
                    },
                )

                if response.status_code >= 400:
                    raise RuntimeError(
                        f"Application failure proxy rejected "
                        f"failure for service '{service.name}': "
                        f"{response.status_code} "
                        f"{response.text}"
                    )

                # Track each service only once because the
                # DELETE endpoint clears all application failures
                # for that service.
                already_tracked = any(
                    service_name == service.name
                    for service_name, _ in (
                        context.application_failures
                    )
                )

                if not already_tracked:
                    context.application_failures.append(
                        (
                            service.name,
                            application_proxy_url,
                        )
                    )

                continue

            # ------------------------------------------------
            # DEPENDENCY FAILURE
            # ------------------------------------------------

            if failure.failure_type == DEPENDENCY_FAILURE_TYPE:

                if context.dependency_failures:
                    raise ValueError(
                        "Multiple dependency_error failures "
                        "cannot be active simultaneously."
                    )

                dependency_control_url = (
                    parameters.get(
                        "dependency_control_url"
                    )
                    or dependency_control_url_default
                ).rstrip("/")

                response = await _post_failure(
                    url=(
                        f"{dependency_control_url}/fault"
                    ),
                    payload={
                        "duration_seconds": duration_seconds
                    },
                )

                if response.status_code >= 400:
                    raise RuntimeError(
                        "Dependency service rejected failure: "
                        f"{response.status_code} "
                        f"{response.text}"
                    )

                context.dependency_failures.append(
                    dependency_control_url
                )

                continue

            # ------------------------------------------------
            # INFRASTRUCTURE FAILURE
            # ------------------------------------------------

            if failure.failure_type in INFRASTRUCTURE_FAILURE_TYPES:

                container_name = (
                    service.docker_container_name
                )

                if not container_name:
                    raise ValueError(
                        f"Service '{service.name}' does not "
                        "have a Docker container name configured"
                    )

                task = _create_infrastructure_task(
                    failure=failure,
                    service=service,
                    container_name=container_name,
                    duration_seconds=duration_seconds,
                    parameters=parameters,
                )

                infrastructure_tasks.extend(task)

                continue

            raise ValueError(
                f"Unsupported failure type: "
                f"{failure.failure_type}"
            )

        context.infrastructure_tasks = (
            infrastructure_tasks
        )

        return context

    except Exception:

        context.infrastructure_tasks = (
            infrastructure_tasks
        )

        await cleanup_all_failures(
            context
        )

        raise


def _create_infrastructure_task(
    failure: FailureDB,
    service: Any,
    container_name: str,
    duration_seconds: int,
    parameters: dict,
) -> list[asyncio.Task]:

    failure_type = failure.failure_type

    if failure_type == "cpu_stress":

        return [
            asyncio.create_task(
                inject_cpu_stress(
                    container_name=container_name,
                    duration_seconds=duration_seconds,
                    cpu_workers=parameters.get(
                        "cpu_workers",
                        1,
                    ),
                )
            )
        ]

    if failure_type == "memory_stress":

        return [
            asyncio.create_task(
                inject_memory_stress(
                    container_name=container_name,
                    duration_seconds=duration_seconds,
                    memory_mb=parameters.get(
                        "memory_mb",
                        100,
                    ),
                )
            )
        ]

    if failure_type == "network_delay":

        return [
            asyncio.create_task(
                inject_network_delay(
                    container_name=container_name,
                    delay_ms=parameters.get(
                        "delay_ms",
                        100,
                    ),
                    duration_seconds=duration_seconds,
                )
            )
        ]

    if failure_type == "packet_loss":

        return [
            asyncio.create_task(
                inject_packet_loss(
                    container_name=container_name,
                    loss_percent=parameters.get(
                        "loss_percent",
                        10,
                    ),
                    duration_seconds=duration_seconds,
                )
            )
        ]

    if failure_type == "bandwidth_limit":

        return [
            asyncio.create_task(
                inject_bandwidth_limit(
                    container_name=container_name,
                    bandwidth_mbps=parameters.get(
                        "bandwidth_mbps",
                        10,
                    ),
                    duration_seconds=duration_seconds,
                )
            )
        ]

    if failure_type == "network_partition":

        dependencies = (
            service.outgoing_dependencies
        )

        if not dependencies:
            raise ValueError(
                f"Service '{service.name}' has no outgoing "
                "dependencies for network_partition"
            )

        tasks = []

        for dependency in dependencies:

            target_service = (
                dependency.target_service
            )

            if target_service is None:
                raise ValueError(
                    f"Dependency target for service "
                    f"'{service.name}' was not loaded"
                )

            target_container = (
                target_service.docker_container_name
            )

            if not target_container:
                raise ValueError(
                    f"Target service '{target_service.name}' "
                    "does not have a Docker container name"
                )

            tasks.append(
                asyncio.create_task(
                    inject_network_partition(
                        source_container_name=container_name,
                        target_container_name=target_container,
                        duration_seconds=duration_seconds,
                    )
                )
            )

        return tasks

    if failure_type == "container_crash":

        return [
            asyncio.create_task(
                inject_container_crash(
                    container_name=container_name,
                    duration_seconds=duration_seconds,
                )
            )
        ]

    if failure_type == "disk_stress":

        return [
            asyncio.create_task(
                inject_disk_stress(
                    container_name=container_name,
                    size_mb=parameters.get(
                        "size_mb",
                        100,
                    ),
                    duration_seconds=duration_seconds,
                )
            )
        ]

    raise ValueError(
        f"Unsupported infrastructure failure: "
        f"{failure_type}"
    )


async def stop_multiple_failures(
    context: FailureExecutionContext,
) -> None:

    errors: list[Exception] = []

    for service_name, proxy_url in (
        context.application_failures
    ):

        try:

            response = await _delete_failure(
                f"{proxy_url}/fault/{service_name}"
            )

            if response.status_code >= 400:
                raise RuntimeError(
                    f"Failed to remove application failure "
                    f"for service '{service_name}': "
                    f"{response.status_code} "
                    f"{response.text}"
                )

        except Exception as exc:
            errors.append(exc)

    for dependency_control_url in (
        context.dependency_failures
    ):

        try:

            response = await _delete_failure(
                f"{dependency_control_url}/fault"
            )

            if response.status_code >= 400:
                raise RuntimeError(
                    "Failed to remove dependency failure: "
                    f"{response.status_code} "
                    f"{response.text}"
                )

        except Exception as exc:
            errors.append(exc)

    for task in context.infrastructure_tasks:

        if not task.done():
            task.cancel()

    if context.infrastructure_tasks:

        results = await asyncio.gather(
            *context.infrastructure_tasks,
            return_exceptions=True,
        )

        for result in results:

            if (
                isinstance(result, Exception)
                and not isinstance(
                    result,
                    asyncio.CancelledError,
                )
            ):
                errors.append(result)

    _clear_context(context)

    if errors:
        raise RuntimeError(
            "One or more failures could not be stopped: "
            + "; ".join(
                str(error)
                for error in errors
            )
        )


async def cleanup_all_failures(
    context: FailureExecutionContext,
) -> None:

    for service_name, proxy_url in (
        context.application_failures
    ):

        try:
            await _delete_failure(
                f"{proxy_url}/fault/{service_name}"
            )
        except Exception:
            pass

    for dependency_control_url in (
        context.dependency_failures
    ):

        try:
            await _delete_failure(
                f"{dependency_control_url}/fault"
            )
        except Exception:
            pass

    for task in context.infrastructure_tasks:

        if not task.done():
            task.cancel()

    if context.infrastructure_tasks:

        await asyncio.gather(
            *context.infrastructure_tasks,
            return_exceptions=True,
        )

    _clear_context(context)


async def _post_failure(
    url: str,
    payload: dict,
) -> httpx.Response:

    async with httpx.AsyncClient(
        timeout=10.0
    ) as client:

        return await client.post(
            url,
            json=payload,
        )


async def _delete_failure(
    url: str,
) -> httpx.Response:

    async with httpx.AsyncClient(
        timeout=10.0
    ) as client:

        return await client.delete(url)


def _clear_context(
    context: FailureExecutionContext,
) -> None:

    context.application_failures.clear()
    context.dependency_failures.clear()
    context.infrastructure_tasks.clear()