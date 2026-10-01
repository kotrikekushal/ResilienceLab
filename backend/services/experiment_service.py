from copy import deepcopy
from uuid import UUID
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models.experiment import ExperimentDB
from backend.db.models.failure import FailureDB
from backend.db.models.workload import WorkloadDB
from backend.db.models.system import SystemDB
from backend.db.models.service import ServiceDB


async def clone_experiment(
    db: AsyncSession,
    experiment_id: UUID,
    new_name: str | None = None,
    new_description: str | None = None,
) -> ExperimentDB:
    """
    Create a new experiment by cloning the configuration
    of an existing experiment.

    The existing system, services, and dependencies are reused.
    The workload and failures are copied.
    Executions, metrics, and results are not copied.

    Returns the newly created experiment with its complete
    configuration loaded.
    """

    result = await db.execute(
        select(ExperimentDB)
        .options(
            selectinload(ExperimentDB.workload),
            selectinload(ExperimentDB.failures),
        )
        .where(
            ExperimentDB.id == experiment_id
        )
    )

    source_experiment = result.scalar_one_or_none()

    if source_experiment is None:
        raise ValueError("Experiment not found")

    try:
        # ----------------------------------------------------
        # CREATE NEW EXPERIMENT
        # ----------------------------------------------------

        cloned_experiment = ExperimentDB(
            system_id=source_experiment.system_id,
            name=(
                new_name
                if new_name is not None
                else f"{source_experiment.name} (Clone)"
            ),
            description=(
                new_description
                if new_description is not None
                else source_experiment.description
            ),
            status="created",
            started_at=None,
            finished_at=None,
            error_message=None,
        )

        db.add(cloned_experiment)

        await db.flush()

        # ----------------------------------------------------
        # COPY WORKLOAD
        # ----------------------------------------------------

        if source_experiment.workload is not None:
            cloned_workload = WorkloadDB(
                experiment_id=cloned_experiment.id,
                total_requests=source_experiment.workload.total_requests,
                requests_per_second=(
                    source_experiment.workload.requests_per_second
                ),
                duration_seconds=(
                    source_experiment.workload.duration_seconds
                ),
            )

            db.add(cloned_workload)

        # ----------------------------------------------------
        # COPY FAILURES
        # ----------------------------------------------------

        for source_failure in source_experiment.failures:
            cloned_failure = FailureDB(
                experiment_id=cloned_experiment.id,
                service_id=source_failure.service_id,
                failure_type=source_failure.failure_type,
                duration_seconds=source_failure.duration_seconds,
                parameters=deepcopy(
                    source_failure.parameters
                ),
            )

            db.add(cloned_failure)

        # ----------------------------------------------------
        # SAVE NEW EXPERIMENT
        # ----------------------------------------------------

        await db.commit()

        # ----------------------------------------------------
        # LOAD COMPLETE NEW CONFIGURATION
        # ----------------------------------------------------

        return await get_experiment_configuration(
            db=db,
            experiment_id=cloned_experiment.id,
        )

    except Exception:
        await db.rollback()
        raise


async def reuse_experiment(
    db: AsyncSession,
    experiment_id: UUID,
    new_name: str | None = None,
    new_description: str | None = None,
    workload_overrides: dict[str, Any] | None = None,
    failure_overrides: list[dict[str, Any]] | None = None,
) -> ExperimentDB:
    """
    Create a new experiment from an existing experiment's configuration.

    The existing system, services, and dependencies are reused.

    Workload can be overridden.
    Failures can either be copied or completely replaced.

    The original experiment is never modified.
    Executions, metrics, and results are not copied.

    Returns the newly created experiment with its complete
    configuration loaded.
    """

    result = await db.execute(
        select(ExperimentDB)
        .options(
            selectinload(ExperimentDB.workload),
            selectinload(ExperimentDB.failures),
        )
        .where(
            ExperimentDB.id == experiment_id
        )
    )

    source_experiment = result.scalar_one_or_none()

    if source_experiment is None:
        raise ValueError("Experiment not found")

    try:
        # ----------------------------------------------------
        # CREATE NEW EXPERIMENT
        # ----------------------------------------------------

        reused_experiment = ExperimentDB(
            system_id=source_experiment.system_id,
            name=(
                new_name
                if new_name is not None
                else f"{source_experiment.name} (Reuse)"
            ),
            description=(
                new_description
                if new_description is not None
                else source_experiment.description
            ),
            status="created",
            started_at=None,
            finished_at=None,
            error_message=None,
        )

        db.add(reused_experiment)

        await db.flush()

        # ----------------------------------------------------
        # WORKLOAD
        # ----------------------------------------------------

        if source_experiment.workload is not None:
            source_workload = source_experiment.workload

            workload_data = {
                "total_requests": source_workload.total_requests,
                "requests_per_second": (
                    source_workload.requests_per_second
                ),
                "duration_seconds": (
                    source_workload.duration_seconds
                ),
            }

            # Apply workload changes if provided
            if workload_overrides is not None:
                workload_data.update(workload_overrides)

            reused_workload = WorkloadDB(
                experiment_id=reused_experiment.id,
                total_requests=workload_data["total_requests"],
                requests_per_second=(
                    workload_data["requests_per_second"]
                ),
                duration_seconds=(
                    workload_data["duration_seconds"]
                ),
            )

            db.add(reused_workload)

        # ----------------------------------------------------
        # FAILURES
        # ----------------------------------------------------

        if failure_overrides is not None:

            # Completely replace the original failure configuration
            for failure_data in failure_overrides:
                reused_failure = FailureDB(
                    experiment_id=reused_experiment.id,
                    service_id=failure_data["service_id"],
                    failure_type=failure_data["failure_type"],
                    duration_seconds=failure_data.get(
                        "duration_seconds"
                    ),
                    parameters=deepcopy(
                        failure_data.get("parameters")
                    ),
                )

                db.add(reused_failure)

        else:

            # Copy original failures
            for source_failure in source_experiment.failures:
                reused_failure = FailureDB(
                    experiment_id=reused_experiment.id,
                    service_id=source_failure.service_id,
                    failure_type=source_failure.failure_type,
                    duration_seconds=source_failure.duration_seconds,
                    parameters=deepcopy(
                        source_failure.parameters
                    ),
                )

                db.add(reused_failure)

        # ----------------------------------------------------
        # SAVE NEW EXPERIMENT
        # ----------------------------------------------------

        await db.commit()

        # ----------------------------------------------------
        # LOAD COMPLETE NEW CONFIGURATION
        # ----------------------------------------------------

        return await get_experiment_configuration(
            db=db,
            experiment_id=reused_experiment.id,
        )

    except Exception:
        await db.rollback()
        raise


async def get_experiment_configuration(
    db: AsyncSession,
    experiment_id: UUID,
) -> ExperimentDB:
    """
    Retrieve an experiment together with its complete configuration.

    Configuration includes:

    Experiment
        ├── System
        │   ├── Services
        │   │   └── Dependencies
        │
        ├── Workload
        └── Failures
    """

    result = await db.execute(
        select(ExperimentDB)
        .options(
            # System → Services → Dependencies
            selectinload(
                ExperimentDB.system
            )
            .selectinload(
                SystemDB.services
            )
            .selectinload(
                ServiceDB.outgoing_dependencies
            ),

            # Workload
            selectinload(
                ExperimentDB.workload
            ),

            # Failures
            selectinload(
                ExperimentDB.failures
            ),
        )
        .where(
            ExperimentDB.id == experiment_id
        )
    )

    experiment = result.scalar_one_or_none()

    if experiment is None:
        raise ValueError("Experiment not found")

    return experiment