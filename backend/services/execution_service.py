from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models.metric import MetricDB
from backend.db.models.execution import ExecutionDB


async def get_execution_details(db, execution_id):
    result = await db.execute(
        select(ExecutionDB)
        .options(
            selectinload(ExecutionDB.result),
            selectinload(ExecutionDB.metrics),
        )
        .where(
            ExecutionDB.id == execution_id
        )
    )

    execution = result.scalar_one_or_none()

    if execution is None:
        raise ValueError("Execution not found")

    return execution

async def get_experiment_executions(
    db: AsyncSession,
    experiment_id: UUID,
) -> list[ExecutionDB]:

    result = await db.execute(
        select(ExecutionDB)
        .where(
            ExecutionDB.experiment_id == experiment_id
        )
        .order_by(
            ExecutionDB.run_number
        )
    )

    return list(
        result.scalars().all()
    )


async def get_execution_metrics(
    db: AsyncSession,
    execution_id: UUID,
) -> list[MetricDB]:
    """
    Retrieve all metrics belonging to an execution.
    """

    result = await db.execute(
        select(MetricDB)
        .where(
            MetricDB.execution_id == execution_id
        )
    )

    return list(
        result.scalars().all()
    )