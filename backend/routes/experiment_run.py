import traceback
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from sqlalchemy.orm import selectinload

from backend.db.models.metric import MetricDB
from backend.db.models.result import ResultDB
from backend.services.analysis import analyze_experiment
from backend.db.models.system import SystemDB
from backend.db.models.service import ServiceDB
from backend.db.models.dependency import DependencyDB
from backend.db.models.experiment import ExperimentDB
from backend.db.models.workload import WorkloadDB
from backend.db.models.failure import FailureDB
from backend.db.models.execution import ExecutionDB
from backend.db.models.user import UserDB

from backend.tasks import execute_experiment_task

from backend.models.experiment_run import (
    ExperimentRunCreate,
    ExperimentQueuedResponse,
)

from backend.security.dependencies import get_current_user


router = APIRouter(
    prefix="/experiments",
    tags=["Experiments"],
)


# ============================================================
# OWNERSHIP HELPER
# ============================================================

async def get_owned_experiment(
    db: AsyncSession,
    experiment_id: UUID,
    user_id: UUID,
) -> ExperimentDB:
    """
    Return an experiment only when it belongs to the
    authenticated user through its parent system.
    """

    result = await db.execute(
        select(ExperimentDB)
        .join(
            SystemDB,
            ExperimentDB.system_id == SystemDB.id,
        )
        .where(
            ExperimentDB.id == experiment_id,
            SystemDB.user_id == user_id,
        )
    )

    experiment = result.scalar_one_or_none()

    if experiment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )

    return experiment


# ============================================================
# CREATE AND RUN EXPERIMENT
# ============================================================

@router.post(
    "/run",
    response_model=ExperimentQueuedResponse,
)
async def run_experiment(
    data: ExperimentRunCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    try:
        # ----------------------------------------------------
        # 1. CREATE SYSTEM
        # ----------------------------------------------------

        system = SystemDB(
            user_id=current_user.id,
            name=data.system.name,
            description=data.system.description,
        )

        db.add(system)
        await db.flush()

        # ----------------------------------------------------
        # 2. CREATE SERVICES
        # ----------------------------------------------------

        services = {}

        for service_data in data.services:
            service = ServiceDB(
                system_id=system.id,
                name=service_data.name,
                description=service_data.description,
                base_url=service_data.base_url,
                docker_container_name=(
                    service_data.docker_container_name
                ),
            )

            db.add(service)
            await db.flush()

            services[service.name] = service

        # ----------------------------------------------------
        # 3. CREATE DEPENDENCIES
        # ----------------------------------------------------

        for dependency_data in data.dependencies:
            if dependency_data.source_service not in services:
                raise ValueError(
                    f"Source service not found: "
                    f"{dependency_data.source_service}"
                )

            if dependency_data.target_service not in services:
                raise ValueError(
                    f"Target service not found: "
                    f"{dependency_data.target_service}"
                )

            dependency = DependencyDB(
                source_service_id=services[
                    dependency_data.source_service
                ].id,
                target_service_id=services[
                    dependency_data.target_service
                ].id,
                dependency_type=(
                    dependency_data.dependency_type
                ),
            )

            db.add(dependency)

        # ----------------------------------------------------
        # 4. CREATE EXPERIMENT
        # ----------------------------------------------------

        experiment = ExperimentDB(
            system_id=system.id,
            name=data.experiment.name,
            description=data.experiment.description,
            status="queued",
        )

        db.add(experiment)
        await db.flush()

        # ----------------------------------------------------
        # 5. CREATE WORKLOAD
        # ----------------------------------------------------

        workload = WorkloadDB(
            experiment_id=experiment.id,
            total_requests=data.workload.total_requests,
            requests_per_second=(
                data.workload.requests_per_second
            ),
            duration_seconds=data.workload.duration_seconds,
        )

        db.add(workload)

        # ----------------------------------------------------
        # 6. CREATE FAILURES
        # ----------------------------------------------------

        for failure_data in data.failures:
            if failure_data.service not in services:
                raise ValueError(
                    f"Failure service not found: "
                    f"{failure_data.service}"
                )

            failure = FailureDB(
                experiment_id=experiment.id,
                service_id=services[
                    failure_data.service
                ].id,
                failure_type=failure_data.failure_type,
                duration_seconds=(
                    failure_data.duration_seconds
                ),
                parameters=failure_data.parameters,
            )

            db.add(failure)

        # ----------------------------------------------------
        # 7. SAVE CONFIGURATION
        # ----------------------------------------------------

        await db.commit()

        # ----------------------------------------------------
        # 8. QUEUE CELERY TASK
        # ----------------------------------------------------

        try:
            task = execute_experiment_task.delay(
                str(experiment.id)
            )

        except Exception as exc:
            result = await db.execute(
                select(ExperimentDB).where(
                    ExperimentDB.id == experiment.id
                )
            )

            failed_experiment = result.scalar_one_or_none()

            if failed_experiment is not None:
                failed_experiment.status = "failed"
                failed_experiment.error_message = (
                    f"Failed to queue experiment: {str(exc)}"
                )

                await db.commit()

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to queue experiment",
            )

        # ----------------------------------------------------
        # 9. RETURN QUEUED RESPONSE
        # ----------------------------------------------------

        return {
            "experiment_id": experiment.id,
            "task_id": task.id,
            "status": "queued",
        }

    except HTTPException:
        raise

    except Exception as exc:
        await db.rollback()

        print("\n========== EXPERIMENT ERROR ==========")
        print(str(exc))
        traceback.print_exc()
        print("======================================\n")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Experiment creation failed",
                "error_message": str(exc),
            },
        )


# ============================================================
# RERUN EXISTING EXPERIMENT
# ============================================================

@router.post(
    "/{experiment_id}/rerun",
    response_model=ExperimentQueuedResponse,
)
async def rerun_experiment(
    experiment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    # --------------------------------------------------------
    # 1. LOAD OWNED EXPERIMENT WITH ROW LOCK
    # --------------------------------------------------------

    result = await db.execute(
        select(ExperimentDB)
        .join(
            SystemDB,
            ExperimentDB.system_id == SystemDB.id,
        )
        .where(
            ExperimentDB.id == experiment_id,
            SystemDB.user_id == current_user.id,
        )
        .with_for_update()
    )

    experiment = result.scalar_one_or_none()

    if experiment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )

    # --------------------------------------------------------
    # 2. PREVENT DUPLICATE ACTIVE RUNS
    # --------------------------------------------------------

    if experiment.status in {"queued", "running"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Experiment is already queued or running",
        )

    # --------------------------------------------------------
    # 3. RESET EXECUTION STATE
    # --------------------------------------------------------

    experiment.status = "queued"
    experiment.started_at = None
    experiment.finished_at = None
    experiment.error_message = None

    await db.commit()

    # --------------------------------------------------------
    # 4. QUEUE NEW EXECUTION
    # --------------------------------------------------------

    try:
        task = execute_experiment_task.delay(
            str(experiment.id)
        )

    except Exception as exc:
        result = await db.execute(
            select(ExperimentDB).where(
                ExperimentDB.id == experiment.id
            )
        )

        failed_experiment = result.scalar_one_or_none()

        if failed_experiment is not None:
            failed_experiment.status = "failed"
            failed_experiment.error_message = (
                f"Failed to queue experiment rerun: {str(exc)}"
            )

            await db.commit()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to queue experiment rerun",
        )

    # --------------------------------------------------------
    # 5. RETURN QUEUED RESPONSE
    # --------------------------------------------------------

    return {
        "experiment_id": experiment.id,
        "task_id": task.id,
        "status": "queued",
    }


# ============================================================
# GET EXPERIMENT STATUS
# ============================================================

@router.get("/{experiment_id}/status")
async def get_experiment_status(
    experiment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    # --------------------------------------------------------
    # 1. VERIFY OWNERSHIP
    # --------------------------------------------------------

    experiment = await get_owned_experiment(
        db=db,
        experiment_id=experiment_id,
        user_id=current_user.id,
    )

    # --------------------------------------------------------
    # 2. LOAD EXECUTIONS
    # --------------------------------------------------------

    result = await db.execute(
        select(ExecutionDB)
        .where(
            ExecutionDB.experiment_id == experiment.id
        )
        .order_by(
            ExecutionDB.run_number
        )
    )

    executions = result.scalars().all()

    # --------------------------------------------------------
    # 3. RETURN STATUS
    # --------------------------------------------------------

    return {
        "experiment_id": experiment.id,
        "experiment_name": experiment.name,
        "status": experiment.status,
        "executions": [
            {
                "id": execution.id,
                "run_number": execution.run_number,
                "run_type": execution.run_type,
                "status": execution.status,
                "started_at": execution.started_at,
                "finished_at": execution.finished_at,
                "error_message": execution.error_message,
            }
            for execution in executions
        ],
    }


# ============================================================
# GET COMPLETE EXPERIMENT REPORT
# ============================================================


@router.get("/{experiment_id}/report")
async def get_experiment_report(
    experiment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    # 1. Verify experiment ownership
    experiment = await get_owned_experiment(
        db=db,
        experiment_id=experiment_id,
        user_id=current_user.id,
    )

    # 2. Load executions and their summary results only
    query = await db.execute(
        select(ExecutionDB)
        .options(selectinload(ExecutionDB.result))
        .where(ExecutionDB.experiment_id == experiment.id)
        .order_by(ExecutionDB.run_number)
    )
    executions = list(query.scalars().all())

    # 3. Select the latest execution for each phase
    latest_by_type = {}

    for execution in executions:
        if execution.run_type in {"baseline", "failure", "recovery"}:
            latest_by_type[execution.run_type] = execution

    def serialize_result(execution):
        if execution is None or execution.result is None:
            return None

        result = execution.result

        return {
            "status": execution.status,
            "total_requests": result.total_requests,
            "successful_requests": result.successful_requests,
            "failed_requests": result.failed_requests,
            "success_rate": result.success_rate,
            "error_rate": result.error_rate,
            "average_latency_ms": result.average_latency_ms,
            "p50_latency_ms": result.p50_latency_ms,
            "p95_latency_ms": result.p95_latency_ms,
            "p99_latency_ms": result.p99_latency_ms,
            "throughput": result.throughput,
            "availability": result.availability,
        }

    baseline = latest_by_type.get("baseline")
    failure = latest_by_type.get("failure")
    recovery = latest_by_type.get("recovery")

    # 4. Reconstruct the analysis using the existing analysis service
    analysis = None
    analysis_status = "unavailable"

    required_phases = (baseline, failure, recovery)

    if (
        experiment.status == "completed"
        and all(
            execution is not None
            and execution.status == "completed"
            and execution.result is not None
            for execution in required_phases
        )
    ):
        analysis_input = {
            "experiment_id": str(experiment.id),
            "executions": [
                {
                    "id": execution.id,
                    "experiment_id": experiment.id,
                    "run_number": execution.run_number,
                    "run_type": execution.run_type,
                    "status": execution.status,
                    "started_at": execution.started_at,
                    "finished_at": execution.finished_at,
                    "error_message": execution.error_message,
                    "result": execution.result,
                    "services": [],
                }
                for execution in required_phases
            ],
        }

        try:
            analysis = analyze_experiment(
                analysis_input,
                failures=[],
                recovery_time_seconds=None,
            )
            analysis_status = "reconstructed"
        except (ValueError, KeyError, TypeError, AttributeError):
            analysis_status = "unavailable"

    # 5. Return only the compact report; never return request metrics
    return {
        "experiment_id": str(experiment.id),
        "experiment_name": experiment.name,
        "status": experiment.status,
        "started_at": experiment.started_at,
        "finished_at": experiment.finished_at,
        "error_message": experiment.error_message,
        "baseline": (
            analysis["baseline"]
            if analysis is not None
            else serialize_result(baseline)
        ),
        "failure": (
            analysis["failure"]
            if analysis is not None
            else serialize_result(failure)
        ),
        "recovery": (
            analysis["recovery"]
            if analysis is not None
            else serialize_result(recovery)
        ),
        "overall": (
            analysis["overall"]
            if analysis is not None
            else None
        ),
        "degradation": (
            analysis["degradation"]
            if analysis is not None
            else None
        ),
        "recommendations": (
            analysis["recommendations"]
            if analysis is not None
            else []
        ),
        "analysis_status": analysis_status,
    }
