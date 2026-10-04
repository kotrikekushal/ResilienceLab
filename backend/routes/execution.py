from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db

from backend.db.models.system import SystemDB
from backend.db.models.experiment import ExperimentDB
from backend.db.models.execution import ExecutionDB
from backend.db.models.user import UserDB

from backend.models.experiment_run import (
    ExecutionDetailResponse,
    ExecutionHistoryResponse,
)
from backend.models.metric import MetricResponse

from backend.security.dependencies import get_current_user

from backend.services.execution_service import (
    get_execution_details,
    get_experiment_executions,
    get_execution_metrics,
)


router = APIRouter(
    tags=["Executions"],
)


# ============================================================
# EXECUTION OWNERSHIP HELPER
# ============================================================

async def get_owned_execution(
    db: AsyncSession,
    execution_id: UUID,
    user_id: UUID,
) -> ExecutionDB:
    """
    Return an execution only when it belongs to an experiment
    owned by the authenticated user.

    Ownership path:

        User
          ↓
        System
          ↓
        Experiment
          ↓
        Execution
    """

    result = await db.execute(
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
            ExecutionDB.id == execution_id,
            SystemDB.user_id == user_id,
        )
    )

    execution = result.scalar_one_or_none()

    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )

    return execution


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
    current_user: UserDB = Depends(get_current_user),
):
    await get_owned_execution(
        db=db,
        execution_id=execution_id,
        user_id=current_user.id,
    )

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
    current_user: UserDB = Depends(get_current_user),
):
    # --------------------------------------------------------
    # VERIFY EXPERIMENT OWNERSHIP
    # --------------------------------------------------------

    result = await db.execute(
        select(ExperimentDB)
        .join(
            SystemDB,
            ExperimentDB.system_id == SystemDB.id,
        )
        .where(
            ExperimentDB.id == experiment_id,
            SystemDB.user_id == current_user.id,
        )
    )

    experiment = result.scalar_one_or_none()

    if experiment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )

    # --------------------------------------------------------
    # GET EXECUTIONS
    # --------------------------------------------------------

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
    current_user: UserDB = Depends(get_current_user),
):
    # --------------------------------------------------------
    # VERIFY EXECUTION OWNERSHIP
    # --------------------------------------------------------

    await get_owned_execution(
        db=db,
        execution_id=execution_id,
        user_id=current_user.id,
    )

    # --------------------------------------------------------
    # GET METRICS
    # --------------------------------------------------------

    return await get_execution_metrics(
        db=db,
        execution_id=execution_id,
    )