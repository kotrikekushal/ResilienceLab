import pytest

from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.db.session import get_db

from backend.db.models.system import SystemDB
from backend.db.models.experiment import ExperimentDB
from backend.db.models.execution import ExecutionDB


@pytest.fixture
def override_db(db_session):
    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db

    yield

    app.dependency_overrides.clear()


async def create_test_execution(
    db_session,
    suffix="",
):
    system = SystemDB(
        name=f"Test System{suffix}",
        description="System for result tests",
    )

    db_session.add(system)

    await db_session.flush()

    experiment = ExperimentDB(
        system_id=system.id,
        name=f"Test Experiment{suffix}",
        description="Experiment for result tests",
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

    return execution.id


@pytest.mark.asyncio
async def test_create_result(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        execution_id = await create_test_execution(
            db_session,
            "-create",
        )

        response = await client.post(
            "/results/",
            json={
                "execution_id": str(execution_id),
                "total_requests": 1000,
                "successful_requests": 950,
                "failed_requests": 50,
                "success_rate": 95.0,
                "error_rate": 5.0,
                "average_latency_ms": 125.5,
                "p50_latency_ms": 100.0,
                "p95_latency_ms": 250.0,
                "p99_latency_ms": 400.0,
                "throughput": 100.0,
                "availability": 95.0,
            },
        )

    assert response.status_code == 201

    data = response.json()

    assert data["execution_id"] == str(execution_id)
    assert data["total_requests"] == 1000
    assert data["successful_requests"] == 950
    assert data["failed_requests"] == 50
    assert data["success_rate"] == 95.0
    assert data["error_rate"] == 5.0
    assert data["average_latency_ms"] == 125.5
    assert data["p50_latency_ms"] == 100.0
    assert data["p95_latency_ms"] == 250.0
    assert data["p99_latency_ms"] == 400.0
    assert data["throughput"] == 100.0
    assert data["availability"] == 95.0


@pytest.mark.asyncio
async def test_get_results(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        execution_id_1 = await create_test_execution(
            db_session,
            "-list-1",
        )

        response_1 = await client.post(
            "/results/",
            json={
                "execution_id": str(execution_id_1),
                "total_requests": 100,
                "successful_requests": 90,
                "failed_requests": 10,
                "success_rate": 90.0,
                "error_rate": 10.0,
                "average_latency_ms": 100.0,
                "p50_latency_ms": 80.0,
                "p95_latency_ms": 200.0,
                "p99_latency_ms": 300.0,
                "throughput": 10.0,
                "availability": 90.0,
            },
        )

        assert response_1.status_code == 201

        execution_id_2 = await create_test_execution(
            db_session,
            "-list-2",
        )

        response_2 = await client.post(
            "/results/",
            json={
                "execution_id": str(execution_id_2),
                "total_requests": 200,
                "successful_requests": 180,
                "failed_requests": 20,
                "success_rate": 90.0,
                "error_rate": 10.0,
                "average_latency_ms": 150.0,
                "p50_latency_ms": 120.0,
                "p95_latency_ms": 300.0,
                "p99_latency_ms": 500.0,
                "throughput": 20.0,
                "availability": 90.0,
            },
        )

        assert response_2.status_code == 201

        response = await client.get("/results/")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    assert data[0]["execution_id"] == str(execution_id_1)
    assert data[0]["total_requests"] == 100
    assert data[0]["successful_requests"] == 90
    assert data[0]["failed_requests"] == 10
    assert data[0]["success_rate"] == 90.0
    assert data[0]["error_rate"] == 10.0
    assert data[0]["throughput"] == 10.0
    assert data[0]["availability"] == 90.0

    assert data[1]["execution_id"] == str(execution_id_2)
    assert data[1]["total_requests"] == 200
    assert data[1]["successful_requests"] == 180
    assert data[1]["failed_requests"] == 20
    assert data[1]["success_rate"] == 90.0
    assert data[1]["error_rate"] == 10.0
    assert data[1]["throughput"] == 20.0
    assert data[1]["availability"] == 90.0


@pytest.mark.asyncio
async def test_get_result(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        execution_id = await create_test_execution(
            db_session,
            "-get",
        )

        create_response = await client.post(
            "/results/",
            json={
                "execution_id": str(execution_id),
                "total_requests": 500,
                "successful_requests": 480,
                "failed_requests": 20,
                "success_rate": 96.0,
                "error_rate": 4.0,
                "average_latency_ms": 110.0,
                "p50_latency_ms": 90.0,
                "p95_latency_ms": 220.0,
                "p99_latency_ms": 350.0,
                "throughput": 50.0,
                "availability": 96.0,
            },
        )

        assert create_response.status_code == 201

        result_id = create_response.json()["id"]

        response = await client.get(
            f"/results/{result_id}"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == result_id
    assert data["execution_id"] == str(execution_id)
    assert data["total_requests"] == 500
    assert data["successful_requests"] == 480
    assert data["failed_requests"] == 20
    assert data["success_rate"] == 96.0
    assert data["error_rate"] == 4.0
    assert data["average_latency_ms"] == 110.0
    assert data["p50_latency_ms"] == 90.0
    assert data["p95_latency_ms"] == 220.0
    assert data["p99_latency_ms"] == 350.0
    assert data["throughput"] == 50.0
    assert data["availability"] == 96.0


@pytest.mark.asyncio
async def test_get_result_not_found(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        result_id = "00000000-0000-0000-0000-000000000000"

        response = await client.get(
            f"/results/{result_id}"
        )

    assert response.status_code == 404

    assert response.json()["detail"] == "Result not found"


@pytest.mark.asyncio
async def test_update_result(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        execution_id = await create_test_execution(
            db_session,
            "-update",
        )

        create_response = await client.post(
            "/results/",
            json={
                "execution_id": str(execution_id),
                "total_requests": 100,
                "successful_requests": 90,
                "failed_requests": 10,
                "success_rate": 90.0,
                "error_rate": 10.0,
                "average_latency_ms": 100.0,
                "p50_latency_ms": 80.0,
                "p95_latency_ms": 200.0,
                "p99_latency_ms": 300.0,
                "throughput": 10.0,
                "availability": 90.0,
            },
        )

        assert create_response.status_code == 201

        result_id = create_response.json()["id"]

        response = await client.patch(
            f"/results/{result_id}",
            json={
                "total_requests": 200,
                "successful_requests": 190,
                "failed_requests": 10,
                "success_rate": 95.0,
                "error_rate": 5.0,
                "average_latency_ms": 150.0,
                "p50_latency_ms": 120.0,
                "p95_latency_ms": 300.0,
                "p99_latency_ms": 450.0,
                "throughput": 20.0,
                "availability": 95.0,
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == result_id
    assert data["execution_id"] == str(execution_id)
    assert data["total_requests"] == 200
    assert data["successful_requests"] == 190
    assert data["failed_requests"] == 10
    assert data["success_rate"] == 95.0
    assert data["error_rate"] == 5.0
    assert data["average_latency_ms"] == 150.0
    assert data["p50_latency_ms"] == 120.0
    assert data["p95_latency_ms"] == 300.0
    assert data["p99_latency_ms"] == 450.0
    assert data["throughput"] == 20.0
    assert data["availability"] == 95.0


@pytest.mark.asyncio
async def test_update_result_not_found(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        result_id = "00000000-0000-0000-0000-000000000000"

        response = await client.patch(
            f"/results/{result_id}",
            json={
                "success_rate": 50.0,
            },
        )

    assert response.status_code == 404

    assert response.json()["detail"] == "Result not found"


@pytest.mark.asyncio
async def test_delete_result(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        execution_id = await create_test_execution(
            db_session,
            "-delete",
        )

        create_response = await client.post(
            "/results/",
            json={
                "execution_id": str(execution_id),
                "total_requests": 100,
                "successful_requests": 95,
                "failed_requests": 5,
                "success_rate": 95.0,
                "error_rate": 5.0,
                "average_latency_ms": 100.0,
                "p50_latency_ms": 80.0,
                "p95_latency_ms": 200.0,
                "p99_latency_ms": 300.0,
                "throughput": 10.0,
                "availability": 95.0,
            },
        )

        assert create_response.status_code == 201

        result_id = create_response.json()["id"]

        response = await client.delete(
            f"/results/{result_id}"
        )

        assert response.status_code == 204

        get_response = await client.get(
            f"/results/{result_id}"
        )

    assert get_response.status_code == 404

    assert get_response.json()["detail"] == "Result not found"


@pytest.mark.asyncio
async def test_delete_result_not_found(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        result_id = "00000000-0000-0000-0000-000000000000"

        response = await client.delete(
            f"/results/{result_id}"
        )

    assert response.status_code == 404

    assert response.json()["detail"] == "Result not found"