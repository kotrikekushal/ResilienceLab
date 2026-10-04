from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    ExperimentDB,
    FailureDB,
    SystemDB,
    UserDB,
)
from backend.db.session import get_db
from backend.models.failure import (
    FailureCreate,
    FailureResponse,
    FailureUpdate,
)
from backend.security.dependencies import get_current_user


router = APIRouter(
    prefix="/failures",
    tags=["Failures"],
)


async def get_owned_failure(
    db: AsyncSession,
    failure_id: UUID,
    user_id: UUID,
) -> FailureDB:
    result = await db.execute(
        select(FailureDB)
        .join(
            ExperimentDB,
            FailureDB.experiment_id == ExperimentDB.id,
        )
        .join(
            SystemDB,
            ExperimentDB.system_id == SystemDB.id,
        )
        .where(
            FailureDB.id == failure_id,
            SystemDB.user_id == user_id,
        )
    )

    failure = result.scalar_one_or_none()

    if failure is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Failure not found",
        )

    return failure


@router.post(
    "/",
    response_model=FailureResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_failure(
    data: FailureCreate,
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
    current_user: UserDB = Depends(get_current_user),
):
    result = await db.execute(
        select(FailureDB)
        .join(
            ExperimentDB,
            FailureDB.experiment_id == ExperimentDB.id,
        )
        .join(
            SystemDB,
            ExperimentDB.system_id == SystemDB.id,
        )
        .where(
            SystemDB.user_id == current_user.id,
        )
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
    current_user: UserDB = Depends(get_current_user),
):
    return await get_owned_failure(
        db=db,
        failure_id=failure_id,
        user_id=current_user.id,
    )


@router.patch(
    "/{failure_id}",
    response_model=FailureResponse,
)
async def update_failure(
    failure_id: UUID,
    data: FailureUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    failure = await get_owned_failure(
        db=db,
        failure_id=failure_id,
        user_id=current_user.id,
    )

    update_data = data.model_dump(exclude_unset=True)

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
    current_user: UserDB = Depends(get_current_user),
):
    failure = await get_owned_failure(
        db=db,
        failure_id=failure_id,
        user_id=current_user.id,
    )

    await db.delete(failure)
    await db.commit()

    return None