import pytest
from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.db.session import get_db

from backend.db.models.system import SystemDB
from backend.db.models.service import ServiceDB
from backend.db.models.experiment import ExperimentDB
from backend.db.models.execution import ExecutionDB


@pytest.fixture
def override_db(db_session):
    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db

    yield

    app.dependency_overrides.clear()


async def create_test_execution_and_service(
    db_session,
    suffix="",
):
    system = SystemDB(
        name=f"Test System{suffix}",
        description="System for metric tests",
    )

    db_session.add(system)

    await db_session.flush()

    service = ServiceDB(
        system_id=system.id,
        name=f"Test Service{suffix}",
        description="Service for metric tests",
        base_url="http://target-service",
        docker_container_name="target-service",
    )

    db_session.add(service)

    await db_session.flush()

    experiment = ExperimentDB(
        system_id=system.id,
        name=f"Test Experiment{suffix}",
        description="Experiment for metric tests",
    )

    db_session.add(experiment)

    await db_session.flush()

    execution = ExecutionDB(
        experiment_id=experiment.id,
        run_number=1,
        run_type="baseline",
        status="completed",
    )

    db_session.add(execution)

    await db_session.commit()

    await db_session.refresh(execution)
    await db_session.refresh(service)

    return execution.id, service.id


@pytest.mark.asyncio
async def test_create_metric(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        execution_id, service_id = (
            await create_test_execution_and_service(
                db_session,
                "-create",
            )
        )

        response = await client.post(
            "/metrics/",
            json={
                "execution_id": str(execution_id),
                "service_id": str(service_id),
                "timestamp": "2026-10-02T10:00:00Z",
                "latency_ms": 125.5,
                "status_code": 200,
                "success": True,
                "cpu_usage_percent": 35.5,
                "memory_usage_mb": 256.0,
                "request_count": 100,
                "error_count": 2,
            },
        )

    assert response.status_code == 201

    data = response.json()

    assert data["execution_id"] == str(execution_id)
    assert data["service_id"] == str(service_id)
    assert data["latency_ms"] == 125.5
    assert data["status_code"] == 200
    assert data["success"] is True
    assert data["cpu_usage_percent"] == 35.5
    assert data["memory_usage_mb"] == 256.0
    assert data["request_count"] == 100
    assert data["error_count"] == 2


@pytest.mark.asyncio
async def test_get_metrics(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        execution_id_1, service_id_1 = (
            await create_test_execution_and_service(
                db_session,
                "-list-1",
            )
        )

        response_1 = await client.post(
            "/metrics/",
            json={
                "execution_id": str(execution_id_1),
                "service_id": str(service_id_1),
                "timestamp": "2026-10-02T10:00:00Z",
                "latency_ms": 100.0,
                "status_code": 200,
                "success": True,
                "cpu_usage_percent": 30.0,
                "memory_usage_mb": 200.0,
                "request_count": 50,
                "error_count": 1,
            },
        )

        assert response_1.status_code == 201

        execution_id_2, service_id_2 = (
            await create_test_execution_and_service(
                db_session,
                "-list-2",
            )
        )

        response_2 = await client.post(
            "/metrics/",
            json={
                "execution_id": str(execution_id_2),
                "service_id": str(service_id_2),
                "timestamp": "2026-10-02T11:00:00Z",
                "latency_ms": 250.0,
                "status_code": 500,
                "success": False,
                "cpu_usage_percent": 80.0,
                "memory_usage_mb": 400.0,
                "request_count": 75,
                "error_count": 10,
            },
        )

        assert response_2.status_code == 201

        response = await client.get("/metrics/")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    assert data[0]["execution_id"] == str(execution_id_1)
    assert data[0]["service_id"] == str(service_id_1)
    assert data[0]["latency_ms"] == 100.0
    assert data[0]["status_code"] == 200
    assert data[0]["success"] is True
    assert data[0]["request_count"] == 50
    assert data[0]["error_count"] == 1

    assert data[1]["execution_id"] == str(execution_id_2)
    assert data[1]["service_id"] == str(service_id_2)
    assert data[1]["latency_ms"] == 250.0
    assert data[1]["status_code"] == 500
    assert data[1]["success"] is False
    assert data[1]["request_count"] == 75
    assert data[1]["error_count"] == 10


@pytest.mark.asyncio
async def test_get_metric(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        execution_id, service_id = (
            await create_test_execution_and_service(
                db_session,
                "-get",
            )
        )

        create_response = await client.post(
            "/metrics/",
            json={
                "execution_id": str(execution_id),
                "service_id": str(service_id),
                "timestamp": "2026-10-02T10:00:00Z",
                "latency_ms": 150.0,
                "status_code": 200,
                "success": True,
                "cpu_usage_percent": 40.0,
                "memory_usage_mb": 300.0,
                "request_count": 100,
                "error_count": 0,
            },
        )

        assert create_response.status_code == 201

        metric_id = create_response.json()["id"]

        response = await client.get(
            f"/metrics/{metric_id}"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == metric_id
    assert data["execution_id"] == str(execution_id)
    assert data["service_id"] == str(service_id)
    assert data["latency_ms"] == 150.0
    assert data["status_code"] == 200
    assert data["success"] is True
    assert data["cpu_usage_percent"] == 40.0
    assert data["memory_usage_mb"] == 300.0
    assert data["request_count"] == 100
    assert data["error_count"] == 0


@pytest.mark.asyncio
async def test_get_metric_not_found(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get(
            "/metrics/999999999"
        )

    assert response.status_code == 404

    assert response.json()["detail"] == "Metric not found"


@pytest.mark.asyncio
async def test_update_metric(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        execution_id, service_id = (
            await create_test_execution_and_service(
                db_session,
                "-update",
            )
        )

        create_response = await client.post(
            "/metrics/",
            json={
                "execution_id": str(execution_id),
                "service_id": str(service_id),
                "timestamp": "2026-10-02T10:00:00Z",
                "latency_ms": 100.0,
                "status_code": 200,
                "success": True,
                "cpu_usage_percent": 30.0,
                "memory_usage_mb": 200.0,
                "request_count": 100,
                "error_count": 2,
            },
        )

        assert create_response.status_code == 201

        metric_id = create_response.json()["id"]

        response = await client.patch(
            f"/metrics/{metric_id}",
            json={
                "timestamp": "2026-10-02T12:00:00Z",
                "latency_ms": 300.0,
                "status_code": 500,
                "success": False,
                "cpu_usage_percent": 75.0,
                "memory_usage_mb": 450.0,
                "request_count": 200,
                "error_count": 20,
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == metric_id
    assert data["execution_id"] == str(execution_id)
    assert data["service_id"] == str(service_id)
    assert data["latency_ms"] == 300.0
    assert data["status_code"] == 500
    assert data["success"] is False
    assert data["cpu_usage_percent"] == 75.0
    assert data["memory_usage_mb"] == 450.0
    assert data["request_count"] == 200
    assert data["error_count"] == 20


@pytest.mark.asyncio
async def test_update_metric_not_found(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.patch(
            "/metrics/999999999",
            json={
                "latency_ms": 500.0,
            },
        )

    assert response.status_code == 404

    assert response.json()["detail"] == "Metric not found"


@pytest.mark.asyncio
async def test_delete_metric(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        execution_id, service_id = (
            await create_test_execution_and_service(
                db_session,
                "-delete",
            )
        )

        create_response = await client.post(
            "/metrics/",
            json={
                "execution_id": str(execution_id),
                "service_id": str(service_id),
                "timestamp": "2026-10-02T10:00:00Z",
                "latency_ms": 100.0,
                "status_code": 200,
                "success": True,
                "cpu_usage_percent": 25.0,
                "memory_usage_mb": 150.0,
                "request_count": 50,
                "error_count": 0,
            },
        )

        assert create_response.status_code == 201

        metric_id = create_response.json()["id"]

        response = await client.delete(
            f"/metrics/{metric_id}"
        )

        assert response.status_code == 204

        get_response = await client.get(
            f"/metrics/{metric_id}"
        )

    assert get_response.status_code == 404

    assert get_response.json()["detail"] == "Metric not found"


@pytest.mark.asyncio
async def test_delete_metric_not_found(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.delete(
            "/metrics/999999999"
        )

    assert response.status_code == 404

    assert response.json()["detail"] == "Metric not found"