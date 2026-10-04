from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    ExecutionDB,
    ExperimentDB,
    ResultDB,
    SystemDB,
    UserDB,
)
from backend.db.session import get_db
from backend.models.result import (
    ResultCreate,
    ResultResponse,
    ResultUpdate,
)
from backend.security.dependencies import get_current_user


router = APIRouter(
    prefix="/results",
    tags=["Results"],
)


async def get_owned_result(
    db: AsyncSession,
    result_id: UUID,
    user_id: UUID,
) -> ResultDB:
    query_result = await db.execute(
        select(ResultDB)
        .join(
            ExecutionDB,
            ResultDB.execution_id == ExecutionDB.id,
        )
        .join(
            ExperimentDB,
            ExecutionDB.experiment_id == ExperimentDB.id,
        )
        .join(
            SystemDB,
            ExperimentDB.system_id == SystemDB.id,
        )
        .where(
            ResultDB.id == result_id,
            SystemDB.user_id == user_id,
        )
    )

    result = query_result.scalar_one_or_none()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Result not found",
        )

    return result


@router.post(
    "/",
    response_model=ResultResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_result(
    data: ResultCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    execution_result = await db.execute(
        select(ExecutionDB)
        .join(
            ExperimentDB,
            ExecutionDB.experiment_id == ExperimentDB.id,
        )
        .join(
            SystemDB,
            ExperimentDB.system_id == SystemDB.id,
        )
        .where(
            ExecutionDB.id == data.execution_id,
            SystemDB.user_id == current_user.id,
        )
    )

    execution = execution_result.scalar_one_or_none()

    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )

    result = ResultDB(
        execution_id=data.execution_id,
        total_requests=data.total_requests,
        successful_requests=data.successful_requests,
        failed_requests=data.failed_requests,
        success_rate=data.success_rate,
        error_rate=data.error_rate,
        average_latency_ms=data.average_latency_ms,
        p50_latency_ms=data.p50_latency_ms,
        p95_latency_ms=data.p95_latency_ms,
        p99_latency_ms=data.p99_latency_ms,
        throughput=data.throughput,
        availability=data.availability,
    )

    db.add(result)
    await db.commit()
    await db.refresh(result)

    return result


@router.get(
    "/",
    response_model=list[ResultResponse],
)
async def get_results(
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    query_result = await db.execute(
        select(ResultDB)
        .join(
            ExecutionDB,
            ResultDB.execution_id == ExecutionDB.id,
        )
        .join(
            ExperimentDB,
            ExecutionDB.experiment_id == ExperimentDB.id,
        )
        .join(
            SystemDB,
            ExperimentDB.system_id == SystemDB.id,
        )
        .where(
            SystemDB.user_id == current_user.id,
        )
    )

    results = query_result.scalars().all()

    return results


@router.get(
    "/{result_id}",
    response_model=ResultResponse,
)
async def get_result(
    result_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    return await get_owned_result(
        db=db,
        result_id=result_id,
        user_id=current_user.id,
    )


@router.patch(
    "/{result_id}",
    response_model=ResultResponse,
)
async def update_result(
    result_id: UUID,
    data: ResultUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    result = await get_owned_result(
        db=db,
        result_id=result_id,
        user_id=current_user.id,
    )

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(result, field, value)

    await db.commit()
    await db.refresh(result)

    return result


@router.delete(
    "/{result_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_result(
    result_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    result = await get_owned_result(
        db=db,
        result_id=result_id,
        user_id=current_user.id,
    )

    await db.delete(result)
    await db.commit()

    return None