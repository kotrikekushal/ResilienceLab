from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict
from backend.db.models.result import ResultDB
from backend.db.session import get_db
from backend.models.result import (
    ResultCreate,
    ResultResponse,
    ResultUpdate,
)

router = APIRouter(
    prefix="/results",
    tags=["Results"],
)


@router.post(
    "/",
    response_model=ResultResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_result(
    data: ResultCreate,
    db: AsyncSession = Depends(get_db),
):
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
):
    query_result = await db.execute(
        select(ResultDB)
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
):
    query_result = await db.execute(
        select(ResultDB).where(
            ResultDB.id == result_id
        )
    )

    result = query_result.scalar_one_or_none()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Result not found",
        )

    return result


@router.patch(
    "/{result_id}",
    response_model=ResultResponse,
)
async def update_result(
    result_id: UUID,
    data: ResultUpdate,
    db: AsyncSession = Depends(get_db),
):
    query_result = await db.execute(
        select(ResultDB).where(
            ResultDB.id == result_id
        )
    )

    result = query_result.scalar_one_or_none()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Result not found",
        )

    update_data = data.model_dump(
        exclude_unset=True
    )

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
):
    query_result = await db.execute(
        select(ResultDB).where(
            ResultDB.id == result_id
        )
    )

    result = query_result.scalar_one_or_none()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Result not found",
        )

    await db.delete(result)
    await db.commit()