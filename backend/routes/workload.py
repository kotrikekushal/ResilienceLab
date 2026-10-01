from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.workload import WorkloadDB
from backend.db.session import get_db
from backend.models.workload import (
    WorkloadCreate,
    WorkloadResponse,
    WorkloadUpdate,
)


router = APIRouter(
    prefix="/workloads",
    tags=["Workloads"],
)


@router.post(
    "/",
    response_model=WorkloadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workload(
    data: WorkloadCreate,
    db: AsyncSession = Depends(get_db),
):
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
):
    result = await db.execute(
        select(WorkloadDB)
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
):
    result = await db.execute(
        select(WorkloadDB).where(
            WorkloadDB.id == workload_id
        )
    )

    workload = result.scalar_one_or_none()

    if workload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workload not found",
        )

    return workload


@router.patch(
    "/{workload_id}",
    response_model=WorkloadResponse,
)
async def update_workload(
    workload_id: UUID,
    data: WorkloadUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WorkloadDB).where(
            WorkloadDB.id == workload_id
        )
    )

    workload = result.scalar_one_or_none()

    if workload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workload not found",
        )

    update_data = data.model_dump(
        exclude_unset=True
    )

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
):
    result = await db.execute(
        select(WorkloadDB).where(
            WorkloadDB.id == workload_id
        )
    )

    workload = result.scalar_one_or_none()

    if workload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workload not found",
        )

    await db.delete(workload)

    await db.commit()