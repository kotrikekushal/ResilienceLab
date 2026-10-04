from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    ExecutionDB,
    ExperimentDB,
    MetricDB,
    SystemDB,
    UserDB,
)
from backend.db.session import get_db
from backend.models.metric import (
    MetricCreate,
    MetricResponse,
    MetricUpdate,
)
from backend.security.dependencies import get_current_user


router = APIRouter(
    prefix="/metrics",
    tags=["Metrics"],
)


async def get_owned_metric(
    db: AsyncSession,
    metric_id: int,
    user_id: UUID,
) -> MetricDB:
    result = await db.execute(
        select(MetricDB)
        .join(
            ExecutionDB,
            MetricDB.execution_id == ExecutionDB.id,
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
            MetricDB.id == metric_id,
            SystemDB.user_id == user_id,
        )
    )

    metric = result.scalar_one_or_none()

    if metric is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metric not found",
        )

    return metric


@router.post(
    "/",
    response_model=MetricResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_metric(
    data: MetricCreate,
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
    current_user: UserDB = Depends(get_current_user),
):
    result = await db.execute(
        select(MetricDB)
        .join(
            ExecutionDB,
            MetricDB.execution_id == ExecutionDB.id,
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

    metrics = result.scalars().all()

    return metrics


@router.get(
    "/{metric_id}",
    response_model=MetricResponse,
)
async def get_metric(
    metric_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    return await get_owned_metric(
        db=db,
        metric_id=metric_id,
        user_id=current_user.id,
    )


@router.patch(
    "/{metric_id}",
    response_model=MetricResponse,
)
async def update_metric(
    metric_id: int,
    data: MetricUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    metric = await get_owned_metric(
        db=db,
        metric_id=metric_id,
        user_id=current_user.id,
    )

    update_data = data.model_dump(exclude_unset=True)

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
    current_user: UserDB = Depends(get_current_user),
):
    metric = await get_owned_metric(
        db=db,
        metric_id=metric_id,
        user_id=current_user.id,
    )

    await db.delete(metric)
    await db.commit()

    return None