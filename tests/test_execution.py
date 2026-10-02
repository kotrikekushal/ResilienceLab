import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.db.session import get_db

from backend.db.models.system import SystemDB
from backend.db.models.service import ServiceDB
from backend.db.models.experiment import ExperimentDB
from backend.db.models.execution import ExecutionDB
from backend.db.models.metric import MetricDB
from backend.db.models.result import ResultDB


@pytest.fixture
def override_db(db_session):
    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db

    yield

    app.dependency_overrides.clear()


async def create_test_execution(db_session):
    """
    Create the required hierarchy:

    System
        ↓
    Service
        ↓
    Experiment
        ↓
    Execution
    """

    system = SystemDB(
        name=f"Test System {uuid.uuid4()}",
        description="System for execution tests",
    )

    db_session.add(system)
    await db_session.flush()

    service = ServiceDB(
        system_id=system.id,
        name=f"Test Service {uuid.uuid4()}",
        description="Service for execution tests",
        base_url="http://test-service",
        docker_container_name="test-service",
    )

    db_session.add(service)
    await db_session.flush()

    experiment = ExperimentDB(
        system_id=system.id,
        name=f"Test Experiment {uuid.uuid4()}",
        description="Experiment for execution tests",
    )

    db_session.add(experiment)
    await db_session.flush()

    execution = ExecutionDB(
        experiment_id=experiment.id,
        run_number=1,
        run_type="baseline",
        status="completed",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )

    db_session.add(execution)

    await db_session.commit()
    await db_session.refresh(execution)

    return {
        "system_id": system.id,
        "service_id": service.id,
        "experiment_id": experiment.id,
        "execution_id": execution.id,
    }


# ============================================================
# GET SINGLE EXECUTION
# ============================================================


@pytest.mark.asyncio
async def test_get_execution(
    db_session,
    override_db,
):
    ids = await create_test_execution(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get(
            f"/executions/{ids['execution_id']}"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == str(ids["execution_id"])
    assert data["experiment_id"] == str(ids["experiment_id"])
    assert data["run_number"] == 1
    assert data["run_type"] == "baseline"
    assert data["status"] == "completed"
    assert data["result"] is None
    assert data["metrics"] == []


@pytest.mark.asyncio
async def test_get_execution_not_found(
    db_session,
    override_db,
):
    execution_id = uuid.uuid4()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get(
            f"/executions/{execution_id}"
        )

    assert response.status_code == 404

    assert response.json()["detail"] == "Execution not found"


# ============================================================
# GET EXPERIMENT EXECUTION HISTORY
# ============================================================


@pytest.mark.asyncio
async def test_get_experiment_execution_history(
    db_session,
    override_db,
):
    ids = await create_test_execution(db_session)

    execution_2 = ExecutionDB(
        experiment_id=ids["experiment_id"],
        run_number=2,
        run_type="failure",
        status="completed",
    )

    execution_3 = ExecutionDB(
        experiment_id=ids["experiment_id"],
        run_number=3,
        run_type="recovery",
        status="completed",
    )

    db_session.add_all(
        [
            execution_2,
            execution_3,
        ]
    )

    await db_session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get(
            f"/experiments/{ids['experiment_id']}/executions"
        )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 3

    assert data[0]["run_number"] == 1
    assert data[0]["run_type"] == "baseline"

    assert data[1]["run_number"] == 2
    assert data[1]["run_type"] == "failure"

    assert data[2]["run_number"] == 3
    assert data[2]["run_type"] == "recovery"


@pytest.mark.asyncio
async def test_get_experiment_execution_history_empty(
    db_session,
    override_db,
):
    system = SystemDB(
        name=f"Empty System {uuid.uuid4()}",
        description="System without executions",
    )

    db_session.add(system)
    await db_session.flush()

    experiment = ExperimentDB(
        system_id=system.id,
        name=f"Empty Experiment {uuid.uuid4()}",
        description="Experiment without executions",
    )

    db_session.add(experiment)

    await db_session.commit()
    await db_session.refresh(experiment)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get(
            f"/experiments/{experiment.id}/executions"
        )

    assert response.status_code == 200

    data = response.json()

    assert data == []


# ============================================================
# GET EXECUTION METRICS
# ============================================================


@pytest.mark.asyncio
async def test_get_execution_metrics(
    db_session,
    override_db,
):
    ids = await create_test_execution(db_session)

    metric_1 = MetricDB(
        execution_id=ids["execution_id"],
        service_id=ids["service_id"],
        timestamp=datetime.now(timezone.utc),
        latency_ms=120.5,
        status_code=200,
        success=True,
        cpu_usage_percent=45.5,
        memory_usage_mb=256.0,
        request_count=10,
        error_count=0,
    )

    metric_2 = MetricDB(
        execution_id=ids["execution_id"],
        service_id=ids["service_id"],
        timestamp=datetime.now(timezone.utc),
        latency_ms=150.5,
        status_code=500,
        success=False,
        cpu_usage_percent=60.0,
        memory_usage_mb=300.0,
        request_count=5,
        error_count=2,
    )

    db_session.add_all(
        [
            metric_1,
            metric_2,
        ]
    )

    await db_session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get(
            f"/executions/{ids['execution_id']}/metrics"
        )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    assert data[0]["execution_id"] == str(
        ids["execution_id"]
    )

    assert data[0]["service_id"] == str(
        ids["service_id"]
    )

    assert data[0]["latency_ms"] == 120.5
    assert data[0]["status_code"] == 200
    assert data[0]["success"] is True

    assert data[1]["latency_ms"] == 150.5
    assert data[1]["status_code"] == 500
    assert data[1]["success"] is False


@pytest.mark.asyncio
async def test_get_execution_metrics_empty(
    db_session,
    override_db,
):
    ids = await create_test_execution(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get(
            f"/executions/{ids['execution_id']}/metrics"
        )

    assert response.status_code == 200

    data = response.json()

    assert data == []