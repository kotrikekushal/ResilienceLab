from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.metric import MetricDB
from backend.db.session import get_db
from backend.models.metric import (
    MetricCreate,
    MetricResponse,
    MetricUpdate,
)

router = APIRouter(
    prefix="/metrics",
    tags=["Metrics"],
)


@router.post(
    "/",
    response_model=MetricResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_metric(
    data: MetricCreate,
    db: AsyncSession = Depends(get_db),
):
    metric = MetricDB(
        execution_id=data.execution_id,
        service_id=data.service_id,
        timestamp=data.timestamp,
        latency_ms=data.latency_ms,
        status_code=data.status_code,
        success=data.success,
        cpu_usage_percent=data.cpu_usage_percent,
        memory_usage_mb=data.memory_usage_mb,
        request_count=data.request_count,
        error_count=data.error_count,
    )

    db.add(metric)
    await db.commit()
    await db.refresh(metric)

    return metric


@router.get(
    "/",
    response_model=list[MetricResponse],
)
async def get_metrics(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MetricDB)
    )

    metrics = result.scalars().all()

    return metrics


@router.get(
    "/{metric_id}",
    response_model=MetricResponse,
)
async def get_metric(
    metric_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MetricDB).where(
            MetricDB.id == metric_id
        )
    )

    metric = result.scalar_one_or_none()

    if metric is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metric not found",
        )

    return metric


@router.patch(
    "/{metric_id}",
    response_model=MetricResponse,
)
async def update_metric(
    metric_id: int,
    data: MetricUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MetricDB).where(
            MetricDB.id == metric_id
        )
    )

    metric = result.scalar_one_or_none()

    if metric is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metric not found",
        )

    update_data = data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(metric, field, value)

    await db.commit()
    await db.refresh(metric)

    return metric


@router.delete(
    "/{metric_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_metric(
    metric_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MetricDB).where(
            MetricDB.id == metric_id
        )
    )

    metric = result.scalar_one_or_none()

    if metric is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metric not found",
        )

    await db.delete(metric)
    await db.commit()