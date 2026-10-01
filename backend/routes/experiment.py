from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.experiment import ExperimentDB
from backend.db.session import get_db

from backend.models.experiment import (
    ExperimentCreate,
    ExperimentResponse,
    ExperimentUpdate,
    ExperimentCloneRequest,
    ExperimentReuseRequest,
    ExperimentConfigurationResponse,
)

from backend.services.experiment_service import (
    clone_experiment,
    reuse_experiment,
    get_experiment_configuration,
)


router = APIRouter(
    prefix="/experiments",
    tags=["Experiments"],
)


# ============================================================
# CREATE EXPERIMENT
# ============================================================

@router.post(
    "/",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_experiment(
    data: ExperimentCreate,
    db: AsyncSession = Depends(get_db),
):
    experiment = ExperimentDB(
        system_id=data.system_id,
        name=data.name,
        description=data.description,
    )

    db.add(experiment)

    await db.commit()
    await db.refresh(experiment)

    return experiment


# ============================================================
# GET ALL EXPERIMENTS
# ============================================================

@router.get(
    "/",
    response_model=list[ExperimentResponse],
)
async def get_experiments(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ExperimentDB)
    )

    experiments = result.scalars().all()

    return experiments


# ============================================================
# CLONE EXPERIMENT
# ============================================================

@router.post(
    "/{experiment_id}/clone",
    response_model=ExperimentConfigurationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def clone_experiment_route(
    experiment_id: UUID,
    data: ExperimentCloneRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        experiment = await clone_experiment(
            db=db,
            experiment_id=experiment_id,
            new_name=data.name,
            new_description=data.description,
        )

        return experiment

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


# ============================================================
# REUSE EXPERIMENT
# ============================================================

@router.post(
    "/{experiment_id}/reuse",
    response_model=ExperimentConfigurationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def reuse_experiment_route(
    experiment_id: UUID,
    data: ExperimentReuseRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        experiment = await reuse_experiment(
            db=db,
            experiment_id=experiment_id,
            new_name=data.name,
            new_description=data.description,
            workload_overrides=data.workload_overrides,
            failure_overrides=data.failure_overrides,
        )

        return experiment

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


# ============================================================
# GET EXPERIMENT CONFIGURATION
# ============================================================

@router.get(
    "/{experiment_id}/configuration",
    response_model=ExperimentConfigurationResponse,
)
async def get_experiment_configuration_route(
    experiment_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    try:
        experiment = await get_experiment_configuration(
            db=db,
            experiment_id=experiment_id,
        )

        return experiment

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


# ============================================================
# GET SINGLE EXPERIMENT
# ============================================================

@router.get(
    "/{experiment_id}",
    response_model=ExperimentResponse,
)
async def get_experiment(
    experiment_id: UUID,
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )

    return experiment


# ============================================================
# UPDATE EXPERIMENT
# ============================================================

@router.patch(
    "/{experiment_id}",
    response_model=ExperimentResponse,
)
async def update_experiment(
    experiment_id: UUID,
    data: ExperimentUpdate,
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )

    update_data = data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(experiment, field, value)

    await db.commit()
    await db.refresh(experiment)

    return experiment


# ============================================================
# DELETE EXPERIMENT
# ============================================================

@router.delete(
    "/{experiment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_experiment(
    experiment_id: UUID,
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )

    await db.delete(experiment)

    await db.commit()

@router.post("/{experiment_id}/cancel")
async def cancel_experiment(
    experiment_id: UUID,
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

    if experiment.status in {
        "completed",
        "failed",
        "cancelled",
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Experiment cannot be cancelled "
                f"because its current status is "
                f"'{experiment.status}'"
            ),
        )

    if experiment.status == "cancel_requested":
        raise HTTPException(
            status_code=409,
            detail="Experiment cancellation is already requested",
        )

    experiment.status = "cancel_requested"

    await db.commit()

    return {
        "experiment_id": experiment.id,
        "status": "cancel_requested",
        "message": "Experiment cancellation requested",
    }
