from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.failure import FailureDB
from backend.db.session import get_db
from backend.models.failure import (
    FailureCreate,
    FailureResponse,
    FailureUpdate,
)


router = APIRouter(
    prefix="/failures",
    tags=["Failures"],
)


@router.post(
    "/",
    response_model=FailureResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_failure(
    data: FailureCreate,
    db: AsyncSession = Depends(get_db),
):
    failure = FailureDB(
        experiment_id=data.experiment_id,
        service_id=data.service_id,
        failure_type=data.failure_type,
        duration_seconds=data.duration_seconds,
        parameters=data.parameters,
    )

    db.add(failure)
    await db.commit()
    await db.refresh(failure)

    return failure


@router.get(
    "/",
    response_model=list[FailureResponse],
)
async def get_failures(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FailureDB)
    )

    failures = result.scalars().all()

    return failures


@router.get(
    "/{failure_id}",
    response_model=FailureResponse,
)
async def get_failure(
    failure_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FailureDB).where(
            FailureDB.id == failure_id
        )
    )

    failure = result.scalar_one_or_none()

    if failure is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Failure not found",
        )

    return failure


@router.patch(
    "/{failure_id}",
    response_model=FailureResponse,
)
async def update_failure(
    failure_id: UUID,
    data: FailureUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FailureDB).where(
            FailureDB.id == failure_id
        )
    )

    failure = result.scalar_one_or_none()

    if failure is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Failure not found",
        )

    update_data = data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(failure, field, value)

    await db.commit()
    await db.refresh(failure)

    return failure


@router.delete(
    "/{failure_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_failure(
    failure_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FailureDB).where(
            FailureDB.id == failure_id
        )
    )

    failure = result.scalar_one_or_none()

    if failure is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Failure not found",
        )

    await db.delete(failure)

    await db.commit()