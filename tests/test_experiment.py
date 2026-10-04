import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.main import app
from backend.db.session import get_db

from backend.db.models.user import UserDB
from backend.db.models.system import SystemDB
from backend.db.models.service import ServiceDB
from backend.db.models.experiment import ExperimentDB

from backend.security.password import hash_password
from backend.security.jwt import create_access_token


# ============================================================
# DATABASE OVERRIDE
# ============================================================


@pytest.fixture
def override_db(db_session):
    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db

    yield

    app.dependency_overrides.clear()


# ============================================================
# AUTH HELPERS
# ============================================================


async def create_test_user(db_session):
    user = UserDB(
        username=f"testuser_{uuid.uuid4().hex[:8]}",
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("StrongPassword@123"),
        is_active=True,
    )

    db_session.add(user)

    await db_session.commit()
    await db_session.refresh(user)

    return user


def get_auth_headers(user):
    token = create_access_token(user.id)

    return {
        "Authorization": f"Bearer {token}",
    }


# ============================================================
# HELPERS
# ============================================================


async def create_test_system(
    db_session,
    user,
):
    system = SystemDB(
        name=f"Test System {uuid.uuid4()}",
        description="System for experiment tests",
        user_id=user.id,
    )

    db_session.add(system)

    await db_session.commit()
    await db_session.refresh(system)

    return system.id


async def create_test_service(
    db_session,
    system_id,
    name,
):
    service = ServiceDB(
        system_id=system_id,
        name=name,
        description=f"{name} service",
        base_url=f"http://{name.lower()}",
        docker_container_name=name.lower(),
    )

    db_session.add(service)

    await db_session.commit()
    await db_session.refresh(service)

    return service.id


async def create_test_experiment(
    client,
    system_id,
    user,
):
    response = await client.post(
        "/experiments/",
        json={
            "system_id": str(system_id),
            "name": "Test Experiment",
            "description": "Experiment for tests",
        },
        headers=get_auth_headers(user),
    )

    assert response.status_code == 201

    return response.json()


async def create_full_experiment(
    client,
    db_session,
    user,
):
    system_id = await create_test_system(
        db_session,
        user,
    )

    service_id = await create_test_service(
        db_session,
        system_id,
        "TargetService",
    )

    experiment = await create_test_experiment(
        client,
        system_id,
        user,
    )

    experiment_id = experiment["id"]

    workload_response = await client.post(
        "/workloads/",
        json={
            "experiment_id": experiment_id,
            "total_requests": 100,
            "requests_per_second": 10,
            "duration_seconds": 10,
        },
    )

    assert workload_response.status_code == 201

    failure_response = await client.post(
        "/failures/",
        json={
            "experiment_id": experiment_id,
            "service_id": str(service_id),
            "failure_type": "latency",
            "duration_seconds": 5,
            "parameters": {
                "delay_ms": 500,
            },
        },
    )

    assert failure_response.status_code == 201

    return experiment, system_id, service_id


# ============================================================
# CREATE EXPERIMENT
# ============================================================


@pytest.mark.asyncio
async def test_create_experiment(
    db_session,
    override_db,
):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        system_id = await create_test_system(
            db_session,
            user,
        )

        response = await client.post(
            "/experiments/",
            json={
                "system_id": str(system_id),
                "name": "Test Experiment",
                "description": "Test description",
            },
            headers=get_auth_headers(user),
        )

    assert response.status_code == 201

    data = response.json()

    assert data["system_id"] == str(system_id)
    assert data["name"] == "Test Experiment"
    assert data["description"] == "Test description"
    assert data["status"] == "created"


# ============================================================
# CREATE EXPERIMENT - SYSTEM NOT OWNED
# ============================================================


@pytest.mark.asyncio
async def test_create_experiment_with_another_users_system(
    db_session,
    override_db,
):
    owner = await create_test_user(db_session)
    other_user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        system_id = await create_test_system(
            db_session,
            owner,
        )

        response = await client.post(
            "/experiments/",
            json={
                "system_id": str(system_id),
                "name": "Unauthorized Experiment",
                "description": "Should not be created",
            },
            headers=get_auth_headers(other_user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "System not found"


# ============================================================
# GET ALL EXPERIMENTS
# ============================================================


@pytest.mark.asyncio
async def test_get_experiments(
    db_session,
    override_db,
):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        system_id = await create_test_system(
            db_session,
            user,
        )

        await create_test_experiment(
            client,
            system_id,
            user,
        )

        response = await client.get(
            "/experiments/",
            headers=get_auth_headers(user),
        )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["name"] == "Test Experiment"


# ============================================================
# GET ALL EXPERIMENTS - USER ISOLATION
# ============================================================


@pytest.mark.asyncio
async def test_get_experiments_returns_only_current_users_experiments(
    db_session,
    override_db,
):
    user_a = await create_test_user(db_session)
    user_b = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        system_a = await create_test_system(
            db_session,
            user_a,
        )

        system_b = await create_test_system(
            db_session,
            user_b,
        )

        await create_test_experiment(
            client,
            system_a,
            user_a,
        )

        await client.post(
            "/experiments/",
            json={
                "system_id": str(system_b),
                "name": "User B Experiment",
                "description": "Owned by B",
            },
            headers=get_auth_headers(user_b),
        )

        response = await client.get(
            "/experiments/",
            headers=get_auth_headers(user_a),
        )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["name"] == "Test Experiment"


# ============================================================
# GET SINGLE EXPERIMENT
# ============================================================


@pytest.mark.asyncio
async def test_get_experiment(
    db_session,
    override_db,
):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        system_id = await create_test_system(
            db_session,
            user,
        )

        experiment = await create_test_experiment(
            client,
            system_id,
            user,
        )

        experiment_id = experiment["id"]

        response = await client.get(
            f"/experiments/{experiment_id}",
            headers=get_auth_headers(user),
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == experiment_id
    assert data["name"] == "Test Experiment"


# ============================================================
# GET SINGLE EXPERIMENT - NOT FOUND
# ============================================================


@pytest.mark.asyncio
async def test_get_experiment_not_found(
    db_session,
    override_db,
):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id = str(uuid.uuid4())

        response = await client.get(
            f"/experiments/{experiment_id}",
            headers=get_auth_headers(user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


# ============================================================
# GET SINGLE EXPERIMENT - OWNERSHIP
# ============================================================


@pytest.mark.asyncio
async def test_user_cannot_get_another_users_experiment(
    db_session,
    override_db,
):
    owner = await create_test_user(db_session)
    other_user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        system_id = await create_test_system(
            db_session,
            owner,
        )

        experiment = await create_test_experiment(
            client,
            system_id,
            owner,
        )

        response = await client.get(
            f"/experiments/{experiment['id']}",
            headers=get_auth_headers(other_user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


# ============================================================
# UPDATE EXPERIMENT
# ============================================================


@pytest.mark.asyncio
async def test_update_experiment(
    db_session,
    override_db,
):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        system_id = await create_test_system(
            db_session,
            user,
        )

        experiment = await create_test_experiment(
            client,
            system_id,
            user,
        )

        experiment_id = experiment["id"]

        response = await client.patch(
            f"/experiments/{experiment_id}",
            json={
                "name": "Updated Experiment",
                "description": "Updated description",
                "error_message": None,
            },
            headers=get_auth_headers(user),
        )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Updated Experiment"
    assert data["description"] == "Updated description"


# ============================================================
# UPDATE EXPERIMENT - NOT FOUND
# ============================================================


@pytest.mark.asyncio
async def test_update_experiment_not_found(
    db_session,
    override_db,
):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id = str(uuid.uuid4())

        response = await client.patch(
            f"/experiments/{experiment_id}",
            json={
                "name": "Updated Experiment",
                "error_message": None,
            },
            headers=get_auth_headers(user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


# ============================================================
# UPDATE EXPERIMENT - OWNERSHIP
# ============================================================


@pytest.mark.asyncio
async def test_user_cannot_update_another_users_experiment(
    db_session,
    override_db,
):
    owner = await create_test_user(db_session)
    other_user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        system_id = await create_test_system(
            db_session,
            owner,
        )

        experiment = await create_test_experiment(
            client,
            system_id,
            owner,
        )

        response = await client.patch(
            f"/experiments/{experiment['id']}",
            json={
                "name": "Hacked Experiment",
            },
            headers=get_auth_headers(other_user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


# ============================================================
# DELETE EXPERIMENT
# ============================================================


@pytest.mark.asyncio
async def test_delete_experiment(
    db_session,
    override_db,
):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        system_id = await create_test_system(
            db_session,
            user,
        )

        experiment = await create_test_experiment(
            client,
            system_id,
            user,
        )

        experiment_id = experiment["id"]

        response = await client.delete(
            f"/experiments/{experiment_id}",
            headers=get_auth_headers(user),
        )

    assert response.status_code == 204


# ============================================================
# DELETE EXPERIMENT - NOT FOUND
# ============================================================


@pytest.mark.asyncio
async def test_delete_experiment_not_found(
    db_session,
    override_db,
):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id = str(uuid.uuid4())

        response = await client.delete(
            f"/experiments/{experiment_id}",
            headers=get_auth_headers(user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


# ============================================================
# DELETE EXPERIMENT - OWNERSHIP
# ============================================================


@pytest.mark.asyncio
async def test_user_cannot_delete_another_users_experiment(
    db_session,
    override_db,
):
    owner = await create_test_user(db_session)
    other_user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        system_id = await create_test_system(
            db_session,
            owner,
        )

        experiment = await create_test_experiment(
            client,
            system_id,
            owner,
        )

        response = await client.delete(
            f"/experiments/{experiment['id']}",
            headers=get_auth_headers(other_user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


# ============================================================
# CLONE EXPERIMENT
# ============================================================


@pytest.mark.asyncio
async def test_clone_experiment(
    db_session,
    override_db,
):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        source, system_id, service_id = (
            await create_full_experiment(
                client,
                db_session,
                user,
            )
        )

        source_id = source["id"]

        response = await client.post(
            f"/experiments/{source_id}/clone",
            json={
                "name": "Cloned Experiment",
                "description": "Cloned description",
            },
            headers=get_auth_headers(user),
        )

    assert response.status_code == 201

    data = response.json()

    assert data["id"] != source_id
    assert data["system_id"] == str(system_id)
    assert data["name"] == "Cloned Experiment"
    assert data["description"] == "Cloned description"
    assert data["status"] == "created"

    assert data["workload"] is not None
    assert data["workload"]["total_requests"] == 100
    assert data["workload"]["requests_per_second"] == 10
    assert data["workload"]["duration_seconds"] == 10

    assert len(data["failures"]) == 1
    assert data["failures"][0]["service_id"] == str(service_id)
    assert data["failures"][0]["failure_type"] == "latency"
    assert data["failures"][0]["duration_seconds"] == 5


# ============================================================
# CLONE EXPERIMENT - NOT FOUND
# ============================================================


@pytest.mark.asyncio
async def test_clone_experiment_not_found(
    db_session,
    override_db,
):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id = str(uuid.uuid4())

        response = await client.post(
            f"/experiments/{experiment_id}/clone",
            json={
                "name": "Cloned Experiment",
            },
            headers=get_auth_headers(user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


# ============================================================
# CLONE EXPERIMENT - OWNERSHIP
# ============================================================


@pytest.mark.asyncio
async def test_user_cannot_clone_another_users_experiment(
    db_session,
    override_db,
):
    owner = await create_test_user(db_session)
    other_user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        source, _, _ = await create_full_experiment(
            client,
            db_session,
            owner,
        )

        response = await client.post(
            f"/experiments/{source['id']}/clone",
            json={
                "name": "Unauthorized Clone",
            },
            headers=get_auth_headers(other_user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


# ============================================================
# REUSE EXPERIMENT
# ============================================================


@pytest.mark.asyncio
async def test_reuse_experiment(
    db_session,
    override_db,
):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        source, system_id, service_id = (
            await create_full_experiment(
                client,
                db_session,
                user,
            )
        )

        source_id = source["id"]

        response = await client.post(
            f"/experiments/{source_id}/reuse",
            json={
                "name": "Reused Experiment",
                "description": "Reused description",
                "workload_overrides": {
                    "total_requests": 200,
                    "requests_per_second": 20,
                    "duration_seconds": 20,
                },
                "failure_overrides": [
                    {
                        "service_id": str(service_id),
                        "failure_type": "error",
                        "duration_seconds": 8,
                        "parameters": {
                            "error_rate": 50,
                        },
                    }
                ],
            },
            headers=get_auth_headers(user),
        )

    assert response.status_code == 201

    data = response.json()

    assert data["id"] != source_id
    assert data["system_id"] == str(system_id)
    assert data["name"] == "Reused Experiment"
    assert data["description"] == "Reused description"
    assert data["status"] == "created"

    assert data["workload"]["total_requests"] == 200
    assert data["workload"]["requests_per_second"] == 20
    assert data["workload"]["duration_seconds"] == 20

    assert len(data["failures"]) == 1
    assert data["failures"][0]["failure_type"] == "error"
    assert data["failures"][0]["duration_seconds"] == 8
    assert data["failures"][0]["parameters"]["error_rate"] == 50


# ============================================================
# REUSE EXPERIMENT - NOT FOUND
# ============================================================


@pytest.mark.asyncio
async def test_reuse_experiment_not_found(
    db_session,
    override_db,
):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id = str(uuid.uuid4())

        response = await client.post(
            f"/experiments/{experiment_id}/reuse",
            json={
                "name": "Reused Experiment",
            },
            headers=get_auth_headers(user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


# ============================================================
# REUSE EXPERIMENT - OWNERSHIP
# ============================================================


@pytest.mark.asyncio
async def test_user_cannot_reuse_another_users_experiment(
    db_session,
    override_db,
):
    owner = await create_test_user(db_session)
    other_user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        source, _, _ = await create_full_experiment(
            client,
            db_session,
            owner,
        )

        response = await client.post(
            f"/experiments/{source['id']}/reuse",
            json={
                "name": "Unauthorized Reuse",
            },
            headers=get_auth_headers(other_user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


# ============================================================
# GET EXPERIMENT CONFIGURATION
# ============================================================


@pytest.mark.asyncio
async def test_get_experiment_configuration(
    db_session,
    override_db,
):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment, system_id, service_id = (
            await create_full_experiment(
                client,
                db_session,
                user,
            )
        )

        experiment_id = experiment["id"]

        response = await client.get(
            f"/experiments/{experiment_id}/configuration",
            headers=get_auth_headers(user),
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == experiment_id
    assert data["system_id"] == str(system_id)

    assert data["system"] is not None
    assert data["system"]["id"] == str(system_id)

    assert len(data["system"]["services"]) == 1
    assert data["system"]["services"][0]["id"] == str(
        service_id
    )

    assert data["workload"] is not None
    assert data["workload"]["total_requests"] == 100

    assert len(data["failures"]) == 1
    assert data["failures"][0]["service_id"] == str(
        service_id
    )


# ============================================================
# CONFIGURATION - NOT FOUND
# ============================================================


@pytest.mark.asyncio
async def test_get_experiment_configuration_not_found(
    db_session,
    override_db,
):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id = str(uuid.uuid4())

        response = await client.get(
            f"/experiments/{experiment_id}/configuration",
            headers=get_auth_headers(user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


# ============================================================
# CONFIGURATION - OWNERSHIP
# ============================================================


@pytest.mark.asyncio
async def test_user_cannot_get_another_users_configuration(
    db_session,
    override_db,
):
    owner = await create_test_user(db_session)
    other_user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        source, _, _ = await create_full_experiment(
            client,
            db_session,
            owner,
        )

        response = await client.get(
            f"/experiments/{source['id']}/configuration",
            headers=get_auth_headers(other_user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


# ============================================================
# CANCEL EXPERIMENT
# ============================================================


@pytest.mark.asyncio
async def test_cancel_experiment(
    db_session,
    override_db,
):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        system_id = await create_test_system(
            db_session,
            user,
        )

        experiment = await create_test_experiment(
            client,
            system_id,
            user,
        )

        experiment_id = experiment["id"]

        response = await client.post(
            f"/experiments/{experiment_id}/cancel",
            headers=get_auth_headers(user),
        )

    assert response.status_code == 200

    data = response.json()

    assert data["experiment_id"] == experiment_id
    assert data["status"] == "cancel_requested"
    assert data["message"] == "Experiment cancellation requested"


# ============================================================
# CANCEL - NOT FOUND
# ============================================================


@pytest.mark.asyncio
async def test_cancel_experiment_not_found(
    db_session,
    override_db,
):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        experiment_id = str(uuid.uuid4())

        response = await client.post(
            f"/experiments/{experiment_id}/cancel",
            headers=get_auth_headers(user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


# ============================================================
# CANCEL - OWNERSHIP
# ============================================================


@pytest.mark.asyncio
async def test_user_cannot_cancel_another_users_experiment(
    db_session,
    override_db,
):
    owner = await create_test_user(db_session)
    other_user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        source, _, _ = await create_full_experiment(
            client,
            db_session,
            owner,
        )

        response = await client.post(
            f"/experiments/{source['id']}/cancel",
            headers=get_auth_headers(other_user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


# ============================================================
# CANCEL COMPLETED EXPERIMENT
# ============================================================


@pytest.mark.asyncio
async def test_cancel_completed_experiment(
    db_session,
    override_db,
):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        system_id = await create_test_system(
            db_session,
            user,
        )

        experiment = await create_test_experiment(
            client,
            system_id,
            user,
        )

        experiment_id = uuid.UUID(
            experiment["id"]
        )

        result = await db_session.execute(
            select(ExperimentDB).where(
                ExperimentDB.id == experiment_id
            )
        )

        db_experiment = result.scalar_one()

        db_experiment.status = "completed"

        await db_session.commit()

        response = await client.post(
            f"/experiments/{experiment_id}/cancel",
            headers=get_auth_headers(user),
        )

    assert response.status_code == 409

    assert (
        response.json()["detail"]
        == "Experiment cannot be cancelled because its current status is 'completed'"
    )


# ============================================================
# CANCEL ALREADY REQUESTED
# ============================================================


@pytest.mark.asyncio
async def test_cancel_already_requested(
    db_session,
    override_db,
):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        system_id = await create_test_system(
            db_session,
            user,
        )

        experiment = await create_test_experiment(
            client,
            system_id,
            user,
        )

        experiment_id = uuid.UUID(
            experiment["id"]
        )

        result = await db_session.execute(
            select(ExperimentDB).where(
                ExperimentDB.id == experiment_id
            )
        )

        db_experiment = result.scalar_one()

        db_experiment.status = "cancel_requested"

        await db_session.commit()

        response = await client.post(
            f"/experiments/{experiment_id}/cancel",
            headers=get_auth_headers(user),
        )

    assert response.status_code == 409

    assert (
        response.json()["detail"]
        == "Experiment cancellation is already requested"
    )


# ============================================================
# AUTHENTICATION
# ============================================================


@pytest.mark.asyncio
async def test_experiment_requires_authentication(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get(
            "/experiments/"
        )

    assert response.status_code == 401