import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.db.session import get_db
from backend.db.models.system import SystemDB
from backend.db.models.experiment import ExperimentDB


@pytest.fixture
def override_db(db_session):
    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db

    yield

    app.dependency_overrides.clear()


async def create_test_experiment(db_session, suffix=""):
    system = SystemDB(
        name=f"Test System{suffix}",
        description="System for workload tests",
    )

    db_session.add(system)
    await db_session.flush()

    experiment = ExperimentDB(
        system_id=system.id,
        name=f"Test Experiment{suffix}",
        description="Experiment for workload tests",
    )

    db_session.add(experiment)

    await db_session.commit()
    await db_session.refresh(experiment)

    return experiment.id


@pytest.mark.asyncio
async def test_create_workload(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id = await create_test_experiment(
            db_session,
            "-create",
        )

        response = await client.post(
            "/workloads/",
            json={
                "experiment_id": str(experiment_id),
                "total_requests": 100,
                "requests_per_second": 10,
                "duration_seconds": 10,
            },
        )

    assert response.status_code == 201

    data = response.json()

    assert data["experiment_id"] == str(experiment_id)
    assert data["total_requests"] == 100
    assert data["requests_per_second"] == 10
    assert data["duration_seconds"] == 10


@pytest.mark.asyncio
async def test_get_workloads(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        # First experiment
        experiment_id_1 = await create_test_experiment(
            db_session,
            "-list-1",
        )

        response_1 = await client.post(
            "/workloads/",
            json={
                "experiment_id": str(experiment_id_1),
                "total_requests": 100,
                "requests_per_second": 10,
                "duration_seconds": 10,
            },
        )

        assert response_1.status_code == 201

        # Second experiment
        experiment_id_2 = await create_test_experiment(
            db_session,
            "-list-2",
        )

        response_2 = await client.post(
            "/workloads/",
            json={
                "experiment_id": str(experiment_id_2),
                "total_requests": 200,
                "requests_per_second": 20,
                "duration_seconds": 10,
            },
        )

        assert response_2.status_code == 201

        # Get all workloads
        response = await client.get("/workloads/")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    assert data[0]["experiment_id"] == str(experiment_id_1)
    assert data[0]["total_requests"] == 100
    assert data[0]["requests_per_second"] == 10
    assert data[0]["duration_seconds"] == 10

    assert data[1]["experiment_id"] == str(experiment_id_2)
    assert data[1]["total_requests"] == 200
    assert data[1]["requests_per_second"] == 20
    assert data[1]["duration_seconds"] == 10


@pytest.mark.asyncio
async def test_get_workload(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id = await create_test_experiment(
            db_session,
            "-get",
        )

        create_response = await client.post(
            "/workloads/",
            json={
                "experiment_id": str(experiment_id),
                "total_requests": 100,
                "requests_per_second": 10,
                "duration_seconds": 10,
            },
        )

        assert create_response.status_code == 201

        workload_id = create_response.json()["id"]

        response = await client.get(
            f"/workloads/{workload_id}"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == workload_id
    assert data["experiment_id"] == str(experiment_id)
    assert data["total_requests"] == 100
    assert data["requests_per_second"] == 10
    assert data["duration_seconds"] == 10


@pytest.mark.asyncio
async def test_get_workload_not_found(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get(
            "/workloads/00000000-0000-0000-0000-000000000000"
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Workload not found"


@pytest.mark.asyncio
async def test_update_workload(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id = await create_test_experiment(
            db_session,
            "-update",
        )

        create_response = await client.post(
            "/workloads/",
            json={
                "experiment_id": str(experiment_id),
                "total_requests": 100,
                "requests_per_second": 10,
                "duration_seconds": 10,
            },
        )

        assert create_response.status_code == 201

        workload_id = create_response.json()["id"]

        response = await client.patch(
            f"/workloads/{workload_id}",
            json={
                "total_requests": 500,
                "requests_per_second": 50,
                "duration_seconds": 20,
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == workload_id
    assert data["total_requests"] == 500
    assert data["requests_per_second"] == 50
    assert data["duration_seconds"] == 20


@pytest.mark.asyncio
async def test_update_workload_not_found(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.patch(
            "/workloads/00000000-0000-0000-0000-000000000000",
            json={
                "total_requests": 500,
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Workload not found"


@pytest.mark.asyncio
async def test_delete_workload(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id = await create_test_experiment(
            db_session,
            "-delete",
        )

        create_response = await client.post(
            "/workloads/",
            json={
                "experiment_id": str(experiment_id),
                "total_requests": 100,
                "requests_per_second": 10,
                "duration_seconds": 10,
            },
        )

        assert create_response.status_code == 201

        workload_id = create_response.json()["id"]

        response = await client.delete(
            f"/workloads/{workload_id}"
        )

        assert response.status_code == 204

        get_response = await client.get(
            f"/workloads/{workload_id}"
        )

    assert get_response.status_code == 404
    assert get_response.json()["detail"] == "Workload not found"


@pytest.mark.asyncio
async def test_delete_workload_not_found(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.delete(
            "/workloads/00000000-0000-0000-0000-000000000000"
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Workload not found"


@pytest.mark.asyncio
async def test_create_workload_validation(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id = await create_test_experiment(
            db_session,
            "-validation",
        )

        response = await client.post(
            "/workloads/",
            json={
                "experiment_id": str(experiment_id),
                "total_requests": 0,
                "requests_per_second": 10,
                "duration_seconds": 10,
            },
        )

    assert response.status_code == 422