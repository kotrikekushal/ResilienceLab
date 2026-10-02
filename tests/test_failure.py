import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.db.session import get_db

from backend.db.models.system import SystemDB
from backend.db.models.experiment import ExperimentDB
from backend.db.models.service import ServiceDB


@pytest.fixture
def override_db(db_session):
    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db

    yield

    app.dependency_overrides.clear()


async def create_test_experiment_and_service(
    db_session,
    suffix="",
):
    system = SystemDB(
        name=f"Test System{suffix}",
        description="System for failure tests",
    )

    db_session.add(system)

    await db_session.flush()

    experiment = ExperimentDB(
        system_id=system.id,
        name=f"Test Experiment{suffix}",
        description="Experiment for failure tests",
    )

    service = ServiceDB(
        system_id=system.id,
        name=f"Test Service{suffix}",
        description="Service for failure tests",
        base_url="http://target-service",
        docker_container_name="target-service",
    )

    db_session.add(experiment)
    db_session.add(service)

    await db_session.commit()

    await db_session.refresh(experiment)
    await db_session.refresh(service)

    return experiment.id, service.id


@pytest.mark.asyncio
async def test_create_failure(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id, service_id = (
            await create_test_experiment_and_service(
                db_session,
                "-create",
            )
        )

        response = await client.post(
            "/failures/",
            json={
                "experiment_id": str(experiment_id),
                "service_id": str(service_id),
                "failure_type": "latency",
                "duration_seconds": 10,
                "parameters": {
                    "delay_ms": 500
                },
            },
        )

    assert response.status_code == 201

    data = response.json()

    assert data["experiment_id"] == str(experiment_id)
    assert data["service_id"] == str(service_id)
    assert data["failure_type"] == "latency"
    assert data["duration_seconds"] == 10
    assert data["parameters"] == {
        "delay_ms": 500
    }


@pytest.mark.asyncio
async def test_get_failures(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id_1, service_id_1 = (
            await create_test_experiment_and_service(
                db_session,
                "-list-1",
            )
        )

        response_1 = await client.post(
            "/failures/",
            json={
                "experiment_id": str(experiment_id_1),
                "service_id": str(service_id_1),
                "failure_type": "latency",
                "duration_seconds": 10,
                "parameters": {
                    "delay_ms": 500
                },
            },
        )

        assert response_1.status_code == 201

        experiment_id_2, service_id_2 = (
            await create_test_experiment_and_service(
                db_session,
                "-list-2",
            )
        )

        response_2 = await client.post(
            "/failures/",
            json={
                "experiment_id": str(experiment_id_2),
                "service_id": str(service_id_2),
                "failure_type": "cpu_stress",
                "duration_seconds": 20,
                "parameters": {
                    "cpu_workers": 2
                },
            },
        )

        assert response_2.status_code == 201

        response = await client.get("/failures/")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    assert data[0]["experiment_id"] == str(experiment_id_1)
    assert data[0]["service_id"] == str(service_id_1)
    assert data[0]["failure_type"] == "latency"
    assert data[0]["duration_seconds"] == 10
    assert data[0]["parameters"] == {
        "delay_ms": 500
    }

    assert data[1]["experiment_id"] == str(experiment_id_2)
    assert data[1]["service_id"] == str(service_id_2)
    assert data[1]["failure_type"] == "cpu_stress"
    assert data[1]["duration_seconds"] == 20
    assert data[1]["parameters"] == {
        "cpu_workers": 2
    }


@pytest.mark.asyncio
async def test_get_failure(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id, service_id = (
            await create_test_experiment_and_service(
                db_session,
                "-get",
            )
        )

        create_response = await client.post(
            "/failures/",
            json={
                "experiment_id": str(experiment_id),
                "service_id": str(service_id),
                "failure_type": "timeout",
                "duration_seconds": 15,
                "parameters": {
                    "timeout_ms": 1000
                },
            },
        )

        assert create_response.status_code == 201

        failure_id = create_response.json()["id"]

        response = await client.get(
            f"/failures/{failure_id}"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == failure_id
    assert data["experiment_id"] == str(experiment_id)
    assert data["service_id"] == str(service_id)
    assert data["failure_type"] == "timeout"
    assert data["duration_seconds"] == 15
    assert data["parameters"] == {
        "timeout_ms": 1000
    }


@pytest.mark.asyncio
async def test_get_failure_not_found(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get(
            "/failures/00000000-0000-0000-0000-000000000000"
        )

    assert response.status_code == 404

    assert response.json()["detail"] == "Failure not found"


@pytest.mark.asyncio
async def test_update_failure(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id, service_id = (
            await create_test_experiment_and_service(
                db_session,
                "-update",
            )
        )

        create_response = await client.post(
            "/failures/",
            json={
                "experiment_id": str(experiment_id),
                "service_id": str(service_id),
                "failure_type": "latency",
                "duration_seconds": 10,
                "parameters": {
                    "delay_ms": 500
                },
            },
        )

        assert create_response.status_code == 201

        failure_id = create_response.json()["id"]

        response = await client.patch(
            f"/failures/{failure_id}",
            json={
                "failure_type": "error",
                "duration_seconds": 20,
                "parameters": {
                    "status_code": 500
                },
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == failure_id
    assert data["experiment_id"] == str(experiment_id)
    assert data["service_id"] == str(service_id)
    assert data["failure_type"] == "error"
    assert data["duration_seconds"] == 20
    assert data["parameters"] == {
        "status_code": 500
    }


@pytest.mark.asyncio
async def test_update_failure_not_found(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.patch(
            "/failures/00000000-0000-0000-0000-000000000000",
            json={
                "failure_type": "error",
            },
        )

    assert response.status_code == 404

    assert response.json()["detail"] == "Failure not found"


@pytest.mark.asyncio
async def test_delete_failure(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id, service_id = (
            await create_test_experiment_and_service(
                db_session,
                "-delete",
            )
        )

        create_response = await client.post(
            "/failures/",
            json={
                "experiment_id": str(experiment_id),
                "service_id": str(service_id),
                "failure_type": "timeout",
                "duration_seconds": 10,
                "parameters": {
                    "timeout_ms": 1000
                },
            },
        )

        assert create_response.status_code == 201

        failure_id = create_response.json()["id"]

        response = await client.delete(
            f"/failures/{failure_id}"
        )

        assert response.status_code == 204

        get_response = await client.get(
            f"/failures/{failure_id}"
        )

    assert get_response.status_code == 404

    assert get_response.json()["detail"] == "Failure not found"


@pytest.mark.asyncio
async def test_delete_failure_not_found(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.delete(
            "/failures/00000000-0000-0000-0000-000000000000"
        )

    assert response.status_code == 404

    assert response.json()["detail"] == "Failure not found"


@pytest.mark.asyncio
async def test_create_failure_invalid_type(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id, service_id = (
            await create_test_experiment_and_service(
                db_session,
                "-invalid-type",
            )
        )

        response = await client.post(
            "/failures/",
            json={
                "experiment_id": str(experiment_id),
                "service_id": str(service_id),
                "failure_type": "invalid_failure",
                "duration_seconds": 10,
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_failure_invalid_duration(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id, service_id = (
            await create_test_experiment_and_service(
                db_session,
                "-invalid-duration",
            )
        )

        response = await client.post(
            "/failures/",
            json={
                "experiment_id": str(experiment_id),
                "service_id": str(service_id),
                "failure_type": "latency",
                "duration_seconds": 0,
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_failure_invalid_cpu_parameters(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id, service_id = (
            await create_test_experiment_and_service(
                db_session,
                "-invalid-cpu",
            )
        )

        response = await client.post(
            "/failures/",
            json={
                "experiment_id": str(experiment_id),
                "service_id": str(service_id),
                "failure_type": "cpu_stress",
                "duration_seconds": 10,
                "parameters": {
                    "cpu_workers": 0
                },
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_failure_invalid_packet_loss_parameters(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id, service_id = (
            await create_test_experiment_and_service(
                db_session,
                "-invalid-packet-loss",
            )
        )

        response = await client.post(
            "/failures/",
            json={
                "experiment_id": str(experiment_id),
                "service_id": str(service_id),
                "failure_type": "packet_loss",
                "duration_seconds": 10,
                "parameters": {
                    "loss_percent": 150
                },
            },
        )

    assert response.status_code == 422