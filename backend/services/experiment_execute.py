import asyncio
import statistics
import time
import os
from datetime import datetime
from uuid import UUID

import httpx

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.services.analysis import analyze_experiment

from backend.db.models.system import SystemDB
from backend.db.models.service import ServiceDB
from backend.db.models.dependency import DependencyDB
from backend.db.models.experiment import ExperimentDB
from backend.db.models.metric import MetricDB
from backend.db.models.result import ResultDB
from backend.db.models.execution import ExecutionDB

from backend.services.workload_generator import generate_workload

from backend.services.failure_service import (
    APPLICATION_FAILURE_TYPES,
    start_multiple_failures,
    stop_multiple_failures,
)


# ============================================================
# EXECUTION CREATION
# ============================================================


async def create_execution(
    db: AsyncSession,
    experiment_id: UUID,
    run_type: str,
) -> ExecutionDB:

    result = await db.execute(
        select(func.max(ExecutionDB.run_number)).where(
            ExecutionDB.experiment_id == experiment_id
        )
    )

    last_run_number = result.scalar()

    next_run_number = (
        last_run_number + 1
        if last_run_number is not None
        else 1
    )

    execution = ExecutionDB(
        experiment_id=experiment_id,
        run_number=next_run_number,
        run_type=run_type,
        status="created",
    )

    db.add(execution)

    await db.flush()

    return execution


# ============================================================
# TRUE RECOVERY TIME MEASUREMENT
# ============================================================


async def measure_recovery_time(
    services,
    baseline_services,
    timeout_seconds: float = 30.0,
    probe_interval_seconds: float = 0.25,
    consecutive_healthy_probes: int = 3,
) -> float | None:
    """
    Measures the true recovery time of the system.

    Recovery measurement starts when this function is called.

    A service is considered healthy only when:

    1. The HTTP request succeeds.
    2. The response status code is successful.
    3. The observed latency is within the acceptable
    baseline latency tolerance.

    Recovery is confirmed only after every service has
    remained healthy for the required number of consecutive
    probe rounds.

    Returns:

        float:
            True recovery time in seconds.

        None:
            Recovery was not confirmed before timeout.
    """

    # --------------------------------------------------------
    # BASELINE LATENCY
    # --------------------------------------------------------

    baseline_latency = {
        service["service_id"]: service["average_latency_ms"]
        for service in baseline_services
    }

    # --------------------------------------------------------
    # CONSECUTIVE HEALTHY PROBE COUNTERS
    # --------------------------------------------------------

    healthy_counts = {
        service.id: 0
        for service in services
    }

    # --------------------------------------------------------
    # START TRUE RECOVERY TIMER
    # --------------------------------------------------------

    recovery_start = time.monotonic()

    # --------------------------------------------------------
    # HTTP CLIENT
    # --------------------------------------------------------

    async with httpx.AsyncClient(
        timeout=5.0
    ) as client:

        while True:

            elapsed = (
                time.monotonic()
                - recovery_start
            )

            # ------------------------------------------------
            # RECOVERY TIMEOUT
            # ------------------------------------------------

            if elapsed >= timeout_seconds:
                return None

            # ------------------------------------------------
            # PROBE ONE SERVICE
            # ------------------------------------------------

            async def probe(service):

                request_start = time.monotonic()

                try:

                    response = await client.get(
                        service.base_url
                    )

                    latency_ms = (
                        time.monotonic()
                        - request_start
                    ) * 1000

                    baseline_ms = baseline_latency.get(
                        service.id
                    )

                    # ----------------------------------------
                    # If there is no baseline measurement,
                    # we cannot perform a reliable latency
                    # comparison.
                    # ----------------------------------------

                    if baseline_ms is None:
                        return (
                            service.id,
                            False,
                        )

                    latency_limit = max(
                        baseline_ms * 1.25,
                        baseline_ms + 5.0,
                    )

                    healthy = (
                        response.is_success
                        and latency_ms <= latency_limit
                    )

                    return (
                        service.id,
                        healthy,
                    )

                except Exception:
                    return (
                        service.id,
                        False,
                    )

            # ------------------------------------------------
            # PROBE ALL SERVICES CONCURRENTLY
            # ------------------------------------------------

            probe_results = await asyncio.gather(
                *[
                    probe(service)
                    for service in services
                ]
            )

            # ------------------------------------------------
            # UPDATE HEALTH COUNTERS
            # ------------------------------------------------

            for service_id, healthy in probe_results:

                if healthy:

                    healthy_counts[service_id] += 1

                else:

                    healthy_counts[service_id] = 0

            # ------------------------------------------------
            # CHECK STABLE RECOVERY
            # ------------------------------------------------

            all_services_healthy = all(
                count >= consecutive_healthy_probes
                for count in healthy_counts.values()
            )

            if all_services_healthy:

                return round(
                    time.monotonic()
                    - recovery_start,
                    3,
                )

            # ------------------------------------------------
            # WAIT BEFORE NEXT PROBE
            # ------------------------------------------------

            await asyncio.sleep(
                probe_interval_seconds
            )

async def check_cancellation(
    db: AsyncSession,
    experiment: ExperimentDB,
):
    await db.refresh(experiment)

    if experiment.status == "cancel_requested":
        raise asyncio.CancelledError(
            "Experiment cancellation requested"
        )
    
# ============================================================
# EXPERIMENT LIFECYCLE
# ============================================================


async def execute_experiment(
    db: AsyncSession,
    experiment_id: UUID,
):
    """
    Controls the complete lifecycle of an experiment.

    One experiment contains three executions:

    1. baseline
    2. failure
    3. recovery

    True recovery time is measured between the end of
    the failure condition and confirmed system recovery.
    """

    # --------------------------------------------------------
    # LOAD EXPERIMENT
    # --------------------------------------------------------

    db_result = await db.execute(
        select(ExperimentDB)
        .options(
            selectinload(
                ExperimentDB.system
            )
            .selectinload(
                SystemDB.services
            )
            .selectinload(
                ServiceDB.outgoing_dependencies
            )
            .selectinload(
                DependencyDB.target_service
            ),

            selectinload(
                ExperimentDB.workload
            ),

            selectinload(
                ExperimentDB.failures
            ),
        )
        .where(
            ExperimentDB.id == experiment_id
        )
    )

    experiment = db_result.scalar_one_or_none()

    if experiment is None:
        raise ValueError(
            "Experiment not found"
        )

    if experiment.status == "running":
        raise ValueError(
            "Experiment is already running"
        )

    if experiment.status == "cancel_requested":
        experiment.status = "cancelled"
        experiment.finished_at = datetime.now()
        experiment.error_message = "Experiment cancelled by user"

        await db.commit()

        return {
            "experiment_id": experiment.id,
            "status": "cancelled",
            "executions": [],
            "analysis": None,
        }

    # --------------------------------------------------------
    # MARK EXPERIMENT AS RUNNING
    # --------------------------------------------------------

    experiment.status = "running"
    experiment.started_at = datetime.now()
    experiment.finished_at = None
    experiment.error_message = None

    await db.commit()

    try:

        # ====================================================
        # EXECUTION 1 — BASELINE
        # ====================================================
        await check_cancellation(db, experiment)

        baseline_execution = await create_execution(
            db=db,
            experiment_id=experiment_id,
            run_type="baseline",
        )

        baseline_execution.status = "running"
        baseline_execution.started_at = datetime.now()

        await db.commit()

        try:

            baseline_output = await _run_experiment(
                db=db,
                experiment_id=experiment_id,
                execution=baseline_execution,
                apply_failures=False,
            )

            baseline_execution.status = "completed"
            baseline_execution.finished_at = datetime.now()
            baseline_execution.error_message = None

            await db.commit()

        except Exception as e:

            baseline_execution.status = "failed"
            baseline_execution.finished_at = datetime.now()
            baseline_execution.error_message = str(e)

            await db.commit()

            raise

        # ====================================================
        # EXECUTION 2 — FAILURE
        # ====================================================

        await check_cancellation(db, experiment)

        failure_execution = await create_execution(
            db=db,
            experiment_id=experiment_id,
            run_type="failure",
        )

        failure_execution.status = "running"
        failure_execution.started_at = datetime.now()

        await db.commit()

        try:

            failure_output = await _run_experiment(
                db=db,
                experiment_id=experiment_id,
                execution=failure_execution,
                apply_failures=True,
            )

            failure_execution.status = "completed"
            failure_execution.finished_at = datetime.now()
            failure_execution.error_message = None

            await db.commit()

        except Exception as e:

            failure_execution.status = "failed"
            failure_execution.finished_at = datetime.now()
            failure_execution.error_message = str(e)

            await db.commit()

            raise

        # ====================================================
        # TRUE RECOVERY MEASUREMENT
        # ====================================================

        # The failure execution has completed and all failure injectors
        # have been cleaned up. Recovery measurement begins immediately
        # after the failure condition ends.
        recovery_time_seconds = (
            await measure_recovery_time(
                services=experiment.system.services,
                baseline_services=baseline_output[
                    "services"
                ],
            )
        )

        # ====================================================
        # EXECUTION 3 — RECOVERY
        # ====================================================

        await check_cancellation(db, experiment)

        recovery_execution = await create_execution(
            db=db,
            experiment_id=experiment_id,
            run_type="recovery",
        )

        recovery_execution.status = "running"
        recovery_execution.started_at = datetime.now()

        await db.commit()

        try:

            recovery_output = await _run_experiment(
                db=db,
                experiment_id=experiment_id,
                execution=recovery_execution,
                apply_failures=False,
            )

            recovery_execution.status = "completed"
            recovery_execution.finished_at = datetime.now()
            recovery_execution.error_message = None

            await db.commit()

        except Exception as e:

            recovery_execution.status = "failed"
            recovery_execution.finished_at = datetime.now()
            recovery_execution.error_message = str(e)

            await db.commit()

            raise

        # ====================================================
        # EXPERIMENT COMPLETED
        # ====================================================

        experiment.status = "completed"
        experiment.finished_at = datetime.now()
        experiment.error_message = None

        await db.commit()

        # ====================================================
        # BUILD COMPLETE EXECUTION RESULT
        # ====================================================

        experiment_result = {
            "experiment_id": experiment.id,
            "status": "completed",

            "executions": [

                {
                    "id": baseline_execution.id,
                    "experiment_id": baseline_execution.experiment_id,
                    "run_number": baseline_execution.run_number,
                    "run_type": baseline_execution.run_type,
                    "status": baseline_execution.status,
                    "started_at": baseline_execution.started_at,
                    "finished_at": baseline_execution.finished_at,
                    "error_message": baseline_execution.error_message,
                    "created_at": baseline_execution.created_at,
                    "result": baseline_output["result"],
                    "services": baseline_output["services"],
                },

                {
                    "id": failure_execution.id,
                    "experiment_id": failure_execution.experiment_id,
                    "run_number": failure_execution.run_number,
                    "run_type": failure_execution.run_type,
                    "status": failure_execution.status,
                    "started_at": failure_execution.started_at,
                    "finished_at": failure_execution.finished_at,
                    "error_message": failure_execution.error_message,
                    "created_at": failure_execution.created_at,
                    "result": failure_output["result"],
                    "services": failure_output["services"],
                },

                {
                    "id": recovery_execution.id,
                    "experiment_id": recovery_execution.experiment_id,
                    "run_number": recovery_execution.run_number,
                    "run_type": recovery_execution.run_type,
                    "status": recovery_execution.status,
                    "started_at": recovery_execution.started_at,
                    "finished_at": recovery_execution.finished_at,
                    "error_message": recovery_execution.error_message,
                    "created_at": recovery_execution.created_at,
                    "result": recovery_output["result"],
                    "services": recovery_output["services"],
                },

            ],
        }

        # ====================================================
        # ANALYZE EXPERIMENT
        # ====================================================

        analysis = analyze_experiment(
            experiment_result,
            failures=[
                {
                    "id": failure.id,
                    "service_id": failure.service_id,
                    "failure_type": failure.failure_type,
                    "duration_seconds": failure.duration_seconds,
                    "parameters": failure.parameters,
                }
                for failure in experiment.failures
            ],
            recovery_time_seconds=recovery_time_seconds,
        )

        # ====================================================
        # ADD ANALYSIS
        # ====================================================

        experiment_result["analysis"] = analysis

        return experiment_result
    
    except asyncio.CancelledError:
        experiment.status = "cancelled"
        experiment.error_message = "Experiment cancelled by user"

        await db.commit()

        return {
            "experiment_id": experiment.id,
            "status": "cancelled",
            "executions": [],
            "analysis": None,
        }
    
    except Exception as e:

        # ----------------------------------------------------
        # EXPERIMENT FAILED
        # ----------------------------------------------------

        experiment.status = "failed"
        experiment.finished_at = datetime.now()
        experiment.error_message = str(e)

        await db.commit()

        raise

# ============================================================
# ACTUAL EXECUTION
# ============================================================


async def _run_experiment(
    db: AsyncSession,
    experiment_id: UUID,
    execution: ExecutionDB,
    apply_failures: bool,
):
    """
    Performs one execution of an experiment.

    One execution can be:

    - baseline
    - failure
    - recovery

    When apply_failures=True, every configured failure for the
    experiment is activated through failure_service before any
    workload starts.

    Metrics and result are attached to the execution.
    """

    # --------------------------------------------------------
    # LOAD EXPERIMENT AND RELATED DATA
    # --------------------------------------------------------

    db_result = await db.execute(
        select(ExperimentDB)
        .options(
            selectinload(
                ExperimentDB.system
            )
            .selectinload(
                SystemDB.services
            )
            .selectinload(
                ServiceDB.outgoing_dependencies
            )
            .selectinload(
                DependencyDB.target_service
            ),

            selectinload(
                ExperimentDB.workload
            ),

            selectinload(
                ExperimentDB.failures
            ),
        )
        .where(
            ExperimentDB.id == experiment_id
        )
    )

    experiment = db_result.scalar_one_or_none()

    if experiment is None:
        raise ValueError(
            "Experiment not found"
        )

    # --------------------------------------------------------
    # CHECK WORKLOAD
    # --------------------------------------------------------

    if experiment.workload is None:
        raise ValueError(
            "Experiment does not have a workload configured"
        )

    if experiment.workload.total_requests <= 0:
        raise ValueError(
            "total_requests must be greater than 0"
        )

    if experiment.workload.requests_per_second <= 0:
        raise ValueError(
            "requests_per_second must be greater than 0"
        )

    if experiment.workload.duration_seconds <= 0:
        raise ValueError(
            "duration_seconds must be greater than 0"
        )

    # --------------------------------------------------------
    # CHECK SERVICES
    # --------------------------------------------------------

    if not experiment.system.services:
        raise ValueError(
            "Experiment system does not have any services configured"
        )

    # --------------------------------------------------------
    # CHECK FAILURE SERVICE REFERENCES
    # --------------------------------------------------------

    service_ids = {
        service.id
        for service in experiment.system.services
    }

    for failure in experiment.failures:

        if failure.service_id not in service_ids:
            raise ValueError(
                f"Failure '{failure.id}' references a service "
                "that does not belong to this experiment"
            )

    # --------------------------------------------------------
    # START ALL FAILURES FOR THIS EXECUTION
    # --------------------------------------------------------

    failure_context = None

    if apply_failures:

        failure_context = await start_multiple_failures(
            failures=experiment.failures,
            services=experiment.system.services,
            default_duration_seconds=(
                experiment.workload.duration_seconds
            ),
        )

    # --------------------------------------------------------
    # STORE RESULTS FROM ALL SERVICES
    # --------------------------------------------------------

    all_workload_results = []

    # ========================================================
    # RUN ONE SERVICE
    # ========================================================

    async def run_service_experiment(service):

        # ----------------------------------------------------
        # CHECK WHETHER APPLICATION PROXY IS REQUIRED
        # ----------------------------------------------------

        has_application_failure = any(
            failure.service_id == service.id
            and failure.failure_type in APPLICATION_FAILURE_TYPES
            for failure in experiment.failures
        )

        # ----------------------------------------------------
        # SELECT WORKLOAD TARGET
        # ----------------------------------------------------

        if has_application_failure:

            application_proxy_url = os.getenv(
                "APPLICATION_FAILURE_PROXY_URL",
                "http://application-failure-proxy:8002",
            ).rstrip("/")

            workload_base_url = (
                f"{application_proxy_url}"
                f"/proxy/{service.name}/"
            )

            target_url = service.base_url

        else:

            workload_base_url = service.base_url
            target_url = None

        # ----------------------------------------------------
        # RUN WORKLOAD
        # ----------------------------------------------------

        workload_results = await generate_workload(
            base_url=workload_base_url,

            total_requests=(
                experiment.workload.total_requests
            ),

            requests_per_second=(
                experiment.workload.requests_per_second
            ),

            duration_seconds=(
                experiment.workload.duration_seconds
            ),

            target_url=target_url,
        )

        return {
            "service": service,
            "results": workload_results,
        }

    # ========================================================
    # START EXECUTION TIMER
    # ========================================================

    execution_start_time = time.monotonic()

    try:

        # ====================================================
        # RUN ALL SERVICES CONCURRENTLY
        # ====================================================

        service_tasks = [
            asyncio.create_task(
                run_service_experiment(service)
            )
            for service in experiment.system.services
        ]

        service_results = await asyncio.gather(
            *service_tasks
        )

    finally:

        # ====================================================
        # STOP ALL FAILURES
        # ====================================================

        if failure_context is not None:

            await stop_multiple_failures(
                failure_context
            )

    # ========================================================
    # END EXECUTION TIMER
    # ========================================================

    execution_end_time = time.monotonic()

    actual_execution_time = (
        execution_end_time
        - execution_start_time
    )

    # ========================================================
    # STORE METRICS
    # ========================================================

    for service_result in service_results:

        service = service_result["service"]

        workload_results = service_result["results"]

        for result in workload_results:

            metric = MetricDB(
                execution_id=execution.id,
                service_id=service.id,
                timestamp=datetime.now(),
                latency_ms=(
                    result["latency"] * 1000
                ),
                status_code=result["status_code"],
                success=result["success"],
            )

            db.add(metric)

            all_workload_results.append(
                {
                    "service_id": service.id,
                    "status_code": result["status_code"],
                    "latency": result["latency"],
                    "success": result["success"],
                }
            )

    # ========================================================
    # CALCULATE SERVICE-LEVEL RESULTS
    # ========================================================

    service_summaries = []

    for service_result in service_results:

        service = service_result["service"]

        workload_results = service_result["results"]

        service_total = len(
            workload_results
        )

        service_successful = sum(
            1
            for result in workload_results
            if result["success"]
        )

        service_failed = (
            service_total
            - service_successful
        )

        service_average_latency = (
            sum(
                result["latency"]
                for result in workload_results
            )
            / service_total
            if service_total > 0
            else 0
        )

        service_summaries.append(
            {
                "service_id": service.id,

                "service_name": service.name,

                "total_requests": service_total,

                "successful_requests": (
                    service_successful
                ),

                "failed_requests": service_failed,

                "average_latency_ms": (
                    service_average_latency * 1000
                ),
            }
        )

    # ========================================================
    # CALCULATE BASIC COUNTS
    # ========================================================

    total_requests = len(
        all_workload_results
    )

    successful_requests = sum(
        1
        for result in all_workload_results
        if result["success"]
    )

    failed_requests = (
        total_requests
        - successful_requests
    )

    # ========================================================
    # CALCULATE AVERAGE LATENCY
    # ========================================================

    average_latency = (
        sum(
            result["latency"]
            for result in all_workload_results
        )
        / total_requests
        if total_requests > 0
        else 0
    )

    # ========================================================
    # CREATE LATENCY LIST IN MILLISECONDS
    # ========================================================

    latencies = [
        result["latency"] * 1000
        for result in all_workload_results
    ]

    # ========================================================
    # P50 LATENCY
    # ========================================================

    if len(latencies) >= 2:

        p50_latency = statistics.quantiles(
            latencies,
            n=100,
        )[49]

    elif latencies:

        p50_latency = latencies[0]

    else:

        p50_latency = 0

    # ========================================================
    # P95 LATENCY
    # ========================================================

    if len(latencies) >= 2:

        p95_latency = statistics.quantiles(
            latencies,
            n=100,
        )[94]

    elif latencies:

        p95_latency = latencies[0]

    else:

        p95_latency = 0

    # ========================================================
    # P99 LATENCY
    # ========================================================

    if len(latencies) >= 2:

        p99_latency = statistics.quantiles(
            latencies,
            n=100,
        )[98]

    elif latencies:

        p99_latency = latencies[0]

    else:

        p99_latency = 0

    # ========================================================
    # SUCCESS RATE
    # ========================================================

    success_rate = (
        successful_requests
        / total_requests
        * 100
        if total_requests > 0
        else 0
    )

    # ========================================================
    # ERROR RATE
    # ========================================================

    error_rate = (
        failed_requests
        / total_requests
        * 100
        if total_requests > 0
        else 0
    )

    # ========================================================
    # THROUGHPUT
    # ========================================================

    throughput = (
        total_requests
        / actual_execution_time
        if actual_execution_time > 0
        else 0
    )

    # ========================================================
    # AVAILABILITY
    # ========================================================

    availability = (
        successful_requests
        / total_requests
        * 100
        if total_requests > 0
        else 0
    )

    # ========================================================
    # CREATE RESULT
    # ========================================================

    result = ResultDB(
        execution_id=execution.id,

        total_requests=total_requests,

        successful_requests=successful_requests,

        failed_requests=failed_requests,

        success_rate=success_rate,

        error_rate=error_rate,

        average_latency_ms=(
            average_latency * 1000
        ),

        p50_latency_ms=p50_latency,

        p95_latency_ms=p95_latency,

        p99_latency_ms=p99_latency,

        throughput=throughput,

        availability=availability,
    )

    # ========================================================
    # SAVE RESULT
    # ========================================================

    db.add(result)

    await db.commit()

    # ========================================================
    # RETURN EXECUTION RESULT
    # ========================================================

    return {
        "execution": execution,
        "result": result,
        "services": service_summaries,
    }
