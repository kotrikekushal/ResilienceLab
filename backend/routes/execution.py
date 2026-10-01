from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db

from backend.models.experiment_run import (
    ExecutionDetailResponse,
    ExecutionHistoryResponse,
)
from backend.models.metric import MetricResponse

from backend.services.execution_service import (
    get_execution_details,
    get_experiment_executions,
    get_execution_metrics,
)


router = APIRouter(
    tags=["Executions"],
)


# ============================================================
# GET SINGLE EXECUTION
# ============================================================

@router.get(
    "/executions/{execution_id}",
    response_model=ExecutionDetailResponse,
)
async def get_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    try:
        execution = await get_execution_details(
            db=db,
            execution_id=execution_id,
        )

        return execution

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


# ============================================================
# GET ALL EXECUTIONS OF AN EXPERIMENT
# ============================================================

@router.get(
    "/experiments/{experiment_id}/executions",
    response_model=list[ExecutionHistoryResponse],
)
async def get_experiment_execution_history(
    experiment_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    return await get_experiment_executions(
        db=db,
        experiment_id=experiment_id,
    )


# ============================================================
# GET EXECUTION METRICS
# ============================================================

@router.get(
    "/executions/{execution_id}/metrics",
    response_model=list[MetricResponse],
)
async def get_metrics(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    return await get_execution_metrics(
        db=db,
        execution_id=execution_id,
    )