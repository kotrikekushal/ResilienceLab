from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import traceback

from backend.db.session import get_db
from celery.result import AsyncResult

from backend.celery_app import celery_app

from backend.db.models.system import SystemDB
from backend.db.models.service import ServiceDB
from backend.db.models.dependency import DependencyDB
from backend.db.models.experiment import ExperimentDB
from backend.db.models.workload import WorkloadDB
from backend.db.models.failure import FailureDB
from backend.db.models.execution import ExecutionDB

from backend.tasks import execute_experiment_task

from backend.models.experiment_run import (
    ExperimentRunCreate,
    ExperimentRunResponse,
    ExperimentQueuedResponse,
)

from sqlalchemy import select


router = APIRouter(
    prefix="/experiments",
    tags=["Experiments"],
)


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
):
    try:

        # ====================================================
        # 1. CREATE SYSTEM
        # ====================================================

        system = SystemDB(
            name=data.system.name,
            description=data.system.description,
        )

        db.add(system)

        await db.flush()

        # ====================================================
        # 2. CREATE SERVICES
        # ====================================================

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

        # ====================================================
        # 3. CREATE DEPENDENCIES
        # ====================================================

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

        # ====================================================
        # 4. CREATE EXPERIMENT
        # ====================================================

        experiment = ExperimentDB(
            system_id=system.id,
            name=data.experiment.name,
            description=data.experiment.description,
            status="queued",
        )

        db.add(experiment)

        await db.flush()

        # ====================================================
        # 5. CREATE WORKLOAD
        # ====================================================

        workload = WorkloadDB(
            experiment_id=experiment.id,
            total_requests=data.workload.total_requests,
            requests_per_second=data.workload.requests_per_second,
            duration_seconds=data.workload.duration_seconds,
        )

        db.add(workload)

        # ====================================================
        # 6. CREATE FAILURES
        # ====================================================

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

        # ====================================================
        # 7. SAVE CONFIGURATION
        # ====================================================

        await db.commit()

        # ====================================================
        # 8. QUEUE CELERY TASK
        # ====================================================

        try:
            task = execute_experiment_task.delay(
                str(experiment.id)
            )

        except Exception as e:

            result = await db.execute(
                select(ExperimentDB).where(
                    ExperimentDB.id == experiment.id
                )
            )

            failed_experiment = (
                result.scalar_one_or_none()
            )

            if failed_experiment is not None:
                failed_experiment.status = "failed"
                failed_experiment.error_message = (
                    f"Failed to queue experiment: {str(e)}"
                )

                await db.commit()

            raise HTTPException(
                status_code=503,
                detail="Unable to queue experiment",
            )

        # ====================================================
        # 9. RETURN QUEUED RESPONSE
        # ====================================================

        return {
            "experiment_id": experiment.id,
            "task_id": task.id,
            "status": "queued",
        }

    except HTTPException:
        raise

    except Exception as e:

        await db.rollback()

        print(
            "\n========== EXPERIMENT ERROR =========="
        )

        print(str(e))

        traceback.print_exc()

        print(
            "======================================\n"
        )

        raise HTTPException(
            status_code=500,
            detail={
                "message": "Experiment creation failed",
                "error_message": str(e),
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
    experiment_id: str,
    db: AsyncSession = Depends(get_db),
):
    # ========================================================
    # 1. LOAD EXPERIMENT WITH ROW LOCK
    # ========================================================

    result = await db.execute(
        select(ExperimentDB)
        .where(
            ExperimentDB.id == experiment_id
        )
        .with_for_update()
    )

    experiment = result.scalar_one_or_none()

    if experiment is None:
        raise HTTPException(
            status_code=404,
            detail="Experiment not found",
        )

    # ========================================================
    # 2. PREVENT DUPLICATE ACTIVE RUNS
    # ========================================================

    if experiment.status in {
        "queued",
        "running",
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "Experiment is already queued "
                "or running"
            ),
        )

    # ========================================================
    # 3. RESET CURRENT EXPERIMENT EXECUTION STATE
    # ========================================================

    experiment.status = "queued"
    experiment.started_at = None
    experiment.finished_at = None
    experiment.error_message = None

    await db.commit()

    # ========================================================
    # 4. QUEUE NEW EXECUTION
    # ========================================================

    try:

        task = execute_experiment_task.delay(
            str(experiment.id)
        )

    except Exception as e:

        result = await db.execute(
            select(ExperimentDB).where(
                ExperimentDB.id == experiment.id
            )
        )

        failed_experiment = (
            result.scalar_one_or_none()
        )

        if failed_experiment is not None:
            failed_experiment.status = "failed"
            failed_experiment.error_message = (
                f"Failed to queue rerun: {str(e)}"
            )

            await db.commit()

        raise HTTPException(
            status_code=503,
            detail="Unable to queue experiment rerun",
        )

    # ========================================================
    # 5. RETURN TASK
    # ========================================================

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
    experiment_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ExperimentDB).where(
            ExperimentDB.id == experiment_id
        )
    )

    experiment = result.scalar_one_or_none()

    if experiment is None:
        raise HTTPException(
            status_code=404,
            detail="Experiment not found",
        )

    result = await db.execute(
        select(ExecutionDB)
        .where(
            ExecutionDB.experiment_id == experiment_id
        )
        .order_by(
            ExecutionDB.run_number
        )
    )

    executions = result.scalars().all()

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
# GET CELERY TASK RESULT
# ============================================================

@router.get("/run/{task_id}")
async def get_experiment_result(
    task_id: str,
):
    task = AsyncResult(
        task_id,
        app=celery_app,
    )

    if task.state in {
        "PENDING",
        "STARTED",
        "RETRY",
    }:
        return {
            "task_id": task_id,
            "status": "processing",
        }

    if task.state == "FAILURE":
        return {
            "task_id": task_id,
            "status": "failed",
            "error": str(task.result),
        }

    if task.state == "SUCCESS":
        return {
            "task_id": task_id,
            "status": "completed",
            "result": task.result,
        }

    return {
        "task_id": task_id,
        "status": task.state.lower(),
    }