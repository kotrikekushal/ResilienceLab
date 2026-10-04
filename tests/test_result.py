import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.db.session import get_db
from backend.db.models.user import UserDB
from backend.db.models.system import SystemDB
from backend.db.models.experiment import ExperimentDB
from backend.db.models.execution import ExecutionDB
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


async def create_test_execution(
    db_session,
    user_id,
    suffix="",
):
    system = SystemDB(
        name=f"Test System{suffix}",
        description="System for result tests",
        user_id=user_id,
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
        run_type="manual",
        status="completed",
    )

    db_session.add(execution)

    await db_session.commit()
    await db_session.refresh(execution)

    return execution.id


def auth_headers(user_id):
    token = create_access_token(user_id)

    return {
        "Authorization": f"Bearer {token}",
    }


def result_payload(execution_id):
    return {
        "execution_id": str(execution_id),
        "total_requests": 100,
        "successful_requests": 90,
        "failed_requests": 10,
        "success_rate": 90.0,
        "error_rate": 10.0,
        "average_latency_ms": 50.0,
        "p50_latency_ms": 45.0,
        "p95_latency_ms": 80.0,
        "p99_latency_ms": 100.0,
        "throughput": 10.0,
        "availability": 90.0,
    }


@pytest.mark.asyncio
async def test_create_result(db_session, override_db):
    user = await create_test_user(db_session, "-create")
    headers = auth_headers(user.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        execution_id = await create_test_execution(
            db_session,
            user.id,
            "-create",
        )

        response = await client.post(
            "/results/",
            json=result_payload(execution_id),
            headers=headers,
        )

    assert response.status_code == 201

    data = response.json()

    assert data["execution_id"] == str(execution_id)
    assert data["total_requests"] == 100
    assert data["successful_requests"] == 90
    assert data["failed_requests"] == 10


@pytest.mark.asyncio
async def test_get_results(db_session, override_db):
    user = await create_test_user(db_session, "-list")
    headers = auth_headers(user.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        execution_id_1 = await create_test_execution(
            db_session,
            user.id,
            "-list-1",
        )

        response_1 = await client.post(
            "/results/",
            json=result_payload(execution_id_1),
            headers=headers,
        )

        assert response_1.status_code == 201

        execution_id_2 = await create_test_execution(
            db_session,
            user.id,
            "-list-2",
        )

        payload_2 = result_payload(execution_id_2)
        payload_2["total_requests"] = 200

        response_2 = await client.post(
            "/results/",
            json=payload_2,
            headers=headers,
        )

        assert response_2.status_code == 201

        response = await client.get(
            "/results/",
            headers=headers,
        )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["execution_id"] == str(execution_id_1)
    assert data[1]["execution_id"] == str(execution_id_2)


@pytest.mark.asyncio
async def test_get_result(db_session, override_db):
    user = await create_test_user(db_session, "-get")
    headers = auth_headers(user.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        execution_id = await create_test_execution(
            db_session,
            user.id,
            "-get",
        )

        create_response = await client.post(
            "/results/",
            json=result_payload(execution_id),
            headers=headers,
        )

        assert create_response.status_code == 201

        result_id = create_response.json()["id"]

        response = await client.get(
            f"/results/{result_id}",
            headers=headers,
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == result_id
    assert data["execution_id"] == str(execution_id)


@pytest.mark.asyncio
async def test_get_result_not_found(db_session, override_db):
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
            "/results/00000000-0000-0000-0000-000000000000",
            headers=headers,
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Result not found"


@pytest.mark.asyncio
async def test_update_result(db_session, override_db):
    user = await create_test_user(db_session, "-update")
    headers = auth_headers(user.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        execution_id = await create_test_execution(
            db_session,
            user.id,
            "-update",
        )

        create_response = await client.post(
            "/results/",
            json=result_payload(execution_id),
            headers=headers,
        )

        assert create_response.status_code == 201

        result_id = create_response.json()["id"]

        response = await client.patch(
            f"/results/{result_id}",
            json={
                "total_requests": 500,
                "successful_requests": 450,
                "failed_requests": 50,
            },
            headers=headers,
        )

    assert response.status_code == 200

    data = response.json()

    assert data["total_requests"] == 500
    assert data["successful_requests"] == 450
    assert data["failed_requests"] == 50


@pytest.mark.asyncio
async def test_update_result_not_found(db_session, override_db):
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
            "/results/00000000-0000-0000-0000-000000000000",
            json={
                "total_requests": 500,
            },
            headers=headers,
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Result not found"


@pytest.mark.asyncio
async def test_delete_result(db_session, override_db):
    user = await create_test_user(db_session, "-delete")
    headers = auth_headers(user.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        execution_id = await create_test_execution(
            db_session,
            user.id,
            "-delete",
        )

        create_response = await client.post(
            "/results/",
            json=result_payload(execution_id),
            headers=headers,
        )

        assert create_response.status_code == 201

        result_id = create_response.json()["id"]

        response = await client.delete(
            f"/results/{result_id}",
            headers=headers,
        )

        assert response.status_code == 204

        get_response = await client.get(
            f"/results/{result_id}",
            headers=headers,
        )

    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_result_not_found(db_session, override_db):
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
            "/results/00000000-0000-0000-0000-000000000000",
            headers=headers,
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Result not found"


@pytest.mark.asyncio
async def test_unauthenticated_request(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get("/results/")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cross_user_result_access_denied(
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

        execution_id = await create_test_execution(
            db_session,
            owner.id,
            "-cross-user",
        )

        create_response = await client.post(
            "/results/",
            json=result_payload(execution_id),
            headers=owner_headers,
        )

        assert create_response.status_code == 201

        result_id = create_response.json()["id"]

        get_response = await client.get(
            f"/results/{result_id}",
            headers=attacker_headers,
        )

        assert get_response.status_code == 404

        update_response = await client.patch(
            f"/results/{result_id}",
            json={"total_requests": 999},
            headers=attacker_headers,
        )

        assert update_response.status_code == 404

        delete_response = await client.delete(
            f"/results/{result_id}",
            headers=attacker_headers,
        )

        assert delete_response.status_code == 404


@pytest.mark.asyncio
async def test_create_result_for_other_user_execution_denied(
    db_session,
    override_db,
):
    owner = await create_test_user(
        db_session,
        "-execution-owner",
    )

    attacker = await create_test_user(
        db_session,
        "-execution-attacker",
    )

    attacker_headers = auth_headers(attacker.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        execution_id = await create_test_execution(
            db_session,
            owner.id,
            "-foreign-execution",
        )

        response = await client.post(
            "/results/",
            json=result_payload(execution_id),
            headers=attacker_headers,
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Execution not found"