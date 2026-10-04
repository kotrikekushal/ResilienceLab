import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.db.session import get_db
from backend.db.models.user import UserDB
from backend.db.models.system import SystemDB
from backend.db.models.experiment import ExperimentDB
from backend.db.models.service import ServiceDB
from backend.security.password import hash_password
from backend.security.jwt import create_access_token


@pytest.fixture
def override_db(db_session):
    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db

    yield

    app.dependency_overrides.clear()


async def create_test_user(db_session, suffix=""):
    user = UserDB(
        username=f"testuser{suffix}",
        email=f"test{suffix}@example.com",
        password_hash=hash_password("StrongPassword@123"),
        is_active=True,
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


async def create_test_experiment(
    db_session,
    user_id,
    suffix="",
):
    system = SystemDB(
        name=f"Test System{suffix}",
        description="System for failure tests",
        user_id=user_id,
    )

    db_session.add(system)
    await db_session.flush()

    service = ServiceDB(
        system_id=system.id,
        name=f"Test Service{suffix}",
        description="Service for failure tests",
        base_url="http://test-service:8000",
    )

    db_session.add(service)
    await db_session.flush()

    experiment = ExperimentDB(
        system_id=system.id,
        name=f"Test Experiment{suffix}",
        description="Experiment for failure tests",
    )

    db_session.add(experiment)

    await db_session.commit()
    await db_session.refresh(experiment)

    return experiment.id, service.id


def auth_headers(user_id):
    token = create_access_token(user_id)

    return {
        "Authorization": f"Bearer {token}",
    }


def failure_payload(experiment_id, service_id):
    return {
        "experiment_id": str(experiment_id),
        "service_id": str(service_id),
        "failure_type": "cpu_stress",
        "duration_seconds": 30,
        "parameters": {
            "cpu_percent": 90,
        },
    }


@pytest.mark.asyncio
async def test_create_failure(db_session, override_db):
    user = await create_test_user(db_session, "-create")
    headers = auth_headers(user.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id, service_id = await create_test_experiment(
            db_session,
            user.id,
            "-create",
        )

        response = await client.post(
            "/failures/",
            json=failure_payload(
                experiment_id,
                service_id,
            ),
            headers=headers,
        )

    assert response.status_code == 201

    data = response.json()

    assert data["experiment_id"] == str(experiment_id)
    assert data["service_id"] == str(service_id)
    assert data["failure_type"] == "cpu_stress"
    assert data["duration_seconds"] == 30


@pytest.mark.asyncio
async def test_get_failures(db_session, override_db):
    user = await create_test_user(db_session, "-list")
    headers = auth_headers(user.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id_1, service_id_1 = await create_test_experiment(
            db_session,
            user.id,
            "-list-1",
        )

        response_1 = await client.post(
            "/failures/",
            json=failure_payload(
                experiment_id_1,
                service_id_1,
            ),
            headers=headers,
        )

        assert response_1.status_code == 201

        experiment_id_2, service_id_2 = await create_test_experiment(
            db_session,
            user.id,
            "-list-2",
        )

        response_2 = await client.post(
            "/failures/",
            json=failure_payload(
                experiment_id_2,
                service_id_2,
            ),
            headers=headers,
        )

        assert response_2.status_code == 201

        response = await client.get(
            "/failures/",
            headers=headers,
        )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["experiment_id"] == str(experiment_id_1)
    assert data[1]["experiment_id"] == str(experiment_id_2)


@pytest.mark.asyncio
async def test_get_failure(db_session, override_db):
    user = await create_test_user(db_session, "-get")
    headers = auth_headers(user.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id, service_id = await create_test_experiment(
            db_session,
            user.id,
            "-get",
        )

        create_response = await client.post(
            "/failures/",
            json=failure_payload(
                experiment_id,
                service_id,
            ),
            headers=headers,
        )

        assert create_response.status_code == 201

        failure_id = create_response.json()["id"]

        response = await client.get(
            f"/failures/{failure_id}",
            headers=headers,
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == failure_id
    assert data["experiment_id"] == str(experiment_id)
    assert data["service_id"] == str(service_id)


@pytest.mark.asyncio
async def test_get_failure_not_found(db_session, override_db):
    user = await create_test_user(
        db_session,
        "-get-not-found",
    )

    headers = auth_headers(user.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get(
            "/failures/00000000-0000-0000-0000-000000000000",
            headers=headers,
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Failure not found"


@pytest.mark.asyncio
async def test_update_failure(db_session, override_db):
    user = await create_test_user(db_session, "-update")
    headers = auth_headers(user.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id, service_id = await create_test_experiment(
            db_session,
            user.id,
            "-update",
        )

        create_response = await client.post(
            "/failures/",
            json=failure_payload(
                experiment_id,
                service_id,
            ),
            headers=headers,
        )

        assert create_response.status_code == 201

        failure_id = create_response.json()["id"]

        response = await client.patch(
            f"/failures/{failure_id}",
            json={
                "duration_seconds": 60,
            },
            headers=headers,
        )

    assert response.status_code == 200

    data = response.json()

    assert data["duration_seconds"] == 60


@pytest.mark.asyncio
async def test_update_failure_not_found(db_session, override_db):
    user = await create_test_user(
        db_session,
        "-update-not-found",
    )

    headers = auth_headers(user.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.patch(
            "/failures/00000000-0000-0000-0000-000000000000",
            json={
                "duration_seconds": 60,
            },
            headers=headers,
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Failure not found"


@pytest.mark.asyncio
async def test_delete_failure(db_session, override_db):
    user = await create_test_user(db_session, "-delete")
    headers = auth_headers(user.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id, service_id = await create_test_experiment(
            db_session,
            user.id,
            "-delete",
        )

        create_response = await client.post(
            "/failures/",
            json=failure_payload(
                experiment_id,
                service_id,
            ),
            headers=headers,
        )

        assert create_response.status_code == 201

        failure_id = create_response.json()["id"]

        response = await client.delete(
            f"/failures/{failure_id}",
            headers=headers,
        )

        assert response.status_code == 204

        get_response = await client.get(
            f"/failures/{failure_id}",
            headers=headers,
        )

    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_failure_not_found(db_session, override_db):
    user = await create_test_user(
        db_session,
        "-delete-not-found",
    )

    headers = auth_headers(user.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.delete(
            "/failures/00000000-0000-0000-0000-000000000000",
            headers=headers,
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Failure not found"


@pytest.mark.asyncio
async def test_unauthenticated_request(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get("/failures/")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cross_user_failure_access_denied(
    db_session,
    override_db,
):
    owner = await create_test_user(db_session, "-owner")
    attacker = await create_test_user(db_session, "-attacker")

    owner_headers = auth_headers(owner.id)
    attacker_headers = auth_headers(attacker.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id, service_id = await create_test_experiment(
            db_session,
            owner.id,
            "-cross-user",
        )

        create_response = await client.post(
            "/failures/",
            json=failure_payload(
                experiment_id,
                service_id,
            ),
            headers=owner_headers,
        )

        assert create_response.status_code == 201

        failure_id = create_response.json()["id"]

        get_response = await client.get(
            f"/failures/{failure_id}",
            headers=attacker_headers,
        )

        assert get_response.status_code == 404

        update_response = await client.patch(
            f"/failures/{failure_id}",
            json={"duration_seconds": 999},
            headers=attacker_headers,
        )

        assert update_response.status_code == 404

        delete_response = await client.delete(
            f"/failures/{failure_id}",
            headers=attacker_headers,
        )

        assert delete_response.status_code == 404


@pytest.mark.asyncio
async def test_create_failure_for_other_user_experiment_denied(
    db_session,
    override_db,
):
    owner = await create_test_user(
        db_session,
        "-experiment-owner",
    )

    attacker = await create_test_user(
        db_session,
        "-experiment-attacker",
    )

    attacker_headers = auth_headers(attacker.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id, service_id = await create_test_experiment(
            db_session,
            owner.id,
            "-foreign-experiment",
        )

        response = await client.post(
            "/failures/",
            json=failure_payload(
                experiment_id,
                service_id,
            ),
            headers=attacker_headers,
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"