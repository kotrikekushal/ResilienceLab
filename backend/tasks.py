import asyncio
from uuid import UUID
from fastapi.encoders import jsonable_encoder
from backend.celery_app import celery_app
from backend.db.database import SessionLocal
from backend.services.experiment_execute import execute_experiment


@celery_app.task(
    name="execute_experiment_task",
)
def execute_experiment_task(experiment_id: str):
    return asyncio.run(
        _run_experiment(experiment_id)
    )


async def _run_experiment(experiment_id: str):
    async with SessionLocal() as db:
        result = await execute_experiment(
            db=db,
            experiment_id=UUID(experiment_id),
        )

        return jsonable_encoder(result)