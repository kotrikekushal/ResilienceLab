from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    ExperimentDB,
    SystemDB,
    UserDB,
    WorkloadDB,
)
from backend.db.session import get_db
from backend.models.workload import (
    WorkloadCreate,
    WorkloadResponse,
    WorkloadUpdate,
)
from backend.security.dependencies import get_current_user


router = APIRouter(
    prefix="/workloads",
    tags=["Workloads"],
)


async def get_owned_workload(
    db: AsyncSession,
    workload_id: UUID,
    user_id: UUID,
) -> WorkloadDB:
    result = await db.execute(
        select(WorkloadDB)
        .join(
            ExperimentDB,
            WorkloadDB.experiment_id == ExperimentDB.id,
        )
        .join(
            SystemDB,
            ExperimentDB.system_id == SystemDB.id,
        )
        .where(
            WorkloadDB.id == workload_id,
            SystemDB.user_id == user_id,
        )
    )

    workload = result.scalar_one_or_none()

    if workload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workload not found",
        )

    return workload


@router.post(
    "/",
    response_model=WorkloadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workload(
    data: WorkloadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    experiment_result = await db.execute(
        select(ExperimentDB)
        .join(
            SystemDB,
            ExperimentDB.system_id == SystemDB.id,
        )
        .where(
            ExperimentDB.id == data.experiment_id,
            SystemDB.user_id == current_user.id,
        )
    )

    experiment = experiment_result.scalar_one_or_none()

    if experiment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )

    workload = WorkloadDB(
        experiment_id=data.experiment_id,
        total_requests=data.total_requests,
        requests_per_second=data.requests_per_second,
        duration_seconds=data.duration_seconds,
    )

    db.add(workload)
    await db.commit()
    await db.refresh(workload)

    return workload


@router.get(
    "/",
    response_model=list[WorkloadResponse],
)
async def get_workloads(
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    result = await db.execute(
        select(WorkloadDB)
        .join(
            ExperimentDB,
            WorkloadDB.experiment_id == ExperimentDB.id,
        )
        .join(
            SystemDB,
            ExperimentDB.system_id == SystemDB.id,
        )
        .where(
            SystemDB.user_id == current_user.id,
        )
    )

    workloads = result.scalars().all()

    return workloads


@router.get(
    "/{workload_id}",
    response_model=WorkloadResponse,
)
async def get_workload(
    workload_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    return await get_owned_workload(
        db=db,
        workload_id=workload_id,
        user_id=current_user.id,
    )


@router.patch(
    "/{workload_id}",
    response_model=WorkloadResponse,
)
async def update_workload(
    workload_id: UUID,
    data: WorkloadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    workload = await get_owned_workload(
        db=db,
        workload_id=workload_id,
        user_id=current_user.id,
    )

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(workload, field, value)

    await db.commit()
    await db.refresh(workload)

    return workload


@router.delete(
    "/{workload_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_workload(
    workload_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    workload = await get_owned_workload(
        db=db,
        workload_id=workload_id,
        user_id=current_user.id,
    )

    await db.delete(workload)
    await db.commit()

    return None