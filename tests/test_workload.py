from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    ExperimentDB,
    SystemDB,
    UserDB,
)
from backend.security.jwt import create_access_token
from backend.security.password import hash_password


def workload_payload(experiment_id):
    return {
        "experiment_id": str(experiment_id),
        "total_requests": 300,
        "requests_per_second": 10,
        "duration_seconds": 30,
    }


async def create_user(
    db: AsyncSession,
    suffix: str,
):
    user = UserDB(
        username=f"workload_user_{suffix}",
        email=f"workload_{suffix}@example.com",
        password_hash=hash_password("StrongPassword@123"),
        is_active=True,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


async def create_system(
    db: AsyncSession,
    user: UserDB,
    suffix: str,
):
    system = SystemDB(
        user_id=user.id,
        name=f"Workload System {suffix}",
        description="System for workload tests",
    )

    db.add(system)
    await db.commit()
    await db.refresh(system)

    return system


async def create_experiment(
    db: AsyncSession,
    system: SystemDB,
    suffix: str,
):
    experiment = ExperimentDB(
        system_id=system.id,
        name=f"Workload Experiment {suffix}",
        description="Experiment for workload tests",
        status="created",
    )

    db.add(experiment)
    await db.commit()
    await db.refresh(experiment)

    return experiment


async def auth_headers(user: UserDB):
    token = create_access_token(user.id)

    return {
        "Authorization": f"Bearer {token}",
    }


async def test_create_workload(
    client: AsyncClient,
    db_session: AsyncSession,
):
    user = await create_user(db_session, "create")
    system = await create_system(db_session, user, "create")
    experiment = await create_experiment(
        db_session,
        system,
        "create",
    )

    response = await client.post(
        "/workloads/",
        json=workload_payload(experiment.id),
        headers=await auth_headers(user),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["experiment_id"] == str(experiment.id)
    assert data["total_requests"] == 300
    assert data["requests_per_second"] == 10
    assert data["duration_seconds"] == 30
    assert "id" in data
    assert "created_at" in data


async def test_get_workloads(
    client: AsyncClient,
    db_session: AsyncSession,
):
    user = await create_user(db_session, "list")
    system = await create_system(db_session, user, "list")
    experiment = await create_experiment(
        db_session,
        system,
        "list",
    )

    create_response = await client.post(
        "/workloads/",
        json=workload_payload(experiment.id),
        headers=await auth_headers(user),
    )

    assert create_response.status_code == 201

    response = await client.get(
        "/workloads/",
        headers=await auth_headers(user),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["experiment_id"] == str(experiment.id)


async def test_get_workload(
    client: AsyncClient,
    db_session: AsyncSession,
):
    user = await create_user(db_session, "get")
    system = await create_system(db_session, user, "get")
    experiment = await create_experiment(
        db_session,
        system,
        "get",
    )

    create_response = await client.post(
        "/workloads/",
        json=workload_payload(experiment.id),
        headers=await auth_headers(user),
    )

    assert create_response.status_code == 201

    workload_id = create_response.json()["id"]

    response = await client.get(
        f"/workloads/{workload_id}",
        headers=await auth_headers(user),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == workload_id
    assert data["experiment_id"] == str(experiment.id)


async def test_update_workload(
    client: AsyncClient,
    db_session: AsyncSession,
):
    user = await create_user(db_session, "update")
    system = await create_system(db_session, user, "update")
    experiment = await create_experiment(
        db_session,
        system,
        "update",
    )

    create_response = await client.post(
        "/workloads/",
        json=workload_payload(experiment.id),
        headers=await auth_headers(user),
    )

    assert create_response.status_code == 201

    workload_id = create_response.json()["id"]

    response = await client.patch(
        f"/workloads/{workload_id}",
        json={
            "total_requests": 600,
            "requests_per_second": 20,
            "duration_seconds": 60,
        },
        headers=await auth_headers(user),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_requests"] == 600
    assert data["requests_per_second"] == 20
    assert data["duration_seconds"] == 60


async def test_delete_workload(
    client: AsyncClient,
    db_session: AsyncSession,
):
    user = await create_user(db_session, "delete")
    system = await create_system(db_session, user, "delete")
    experiment = await create_experiment(
        db_session,
        system,
        "delete",
    )

    create_response = await client.post(
        "/workloads/",
        json=workload_payload(experiment.id),
        headers=await auth_headers(user),
    )

    assert create_response.status_code == 201

    workload_id = create_response.json()["id"]

    response = await client.delete(
        f"/workloads/{workload_id}",
        headers=await auth_headers(user),
    )

    assert response.status_code == 204

    get_response = await client.get(
        f"/workloads/{workload_id}",
        headers=await auth_headers(user),
    )

    assert get_response.status_code == 404


async def test_cross_user_workload_access_denied(
    client: AsyncClient,
    db_session: AsyncSession,
):
    owner = await create_user(db_session, "owner")
    other_user = await create_user(db_session, "other")

    system = await create_system(
        db_session,
        owner,
        "cross",
    )

    experiment = await create_experiment(
        db_session,
        system,
        "cross",
    )

    create_response = await client.post(
        "/workloads/",
        json=workload_payload(experiment.id),
        headers=await auth_headers(owner),
    )

    assert create_response.status_code == 201

    workload_id = create_response.json()["id"]

    response = await client.get(
        f"/workloads/{workload_id}",
        headers=await auth_headers(other_user),
    )

    assert response.status_code == 404

    response = await client.patch(
        f"/workloads/{workload_id}",
        json={
            "total_requests": 999,
        },
        headers=await auth_headers(other_user),
    )

    assert response.status_code == 404

    response = await client.delete(
        f"/workloads/{workload_id}",
        headers=await auth_headers(other_user),
    )

    assert response.status_code == 404


async def test_create_workload_for_other_user_experiment_denied(
    client: AsyncClient,
    db_session: AsyncSession,
):
    owner = await create_user(db_session, "experiment_owner")
    other_user = await create_user(db_session, "experiment_other")

    system = await create_system(
        db_session,
        owner,
        "ownership",
    )

    experiment = await create_experiment(
        db_session,
        system,
        "ownership",
    )

    response = await client.post(
        "/workloads/",
        json=workload_payload(experiment.id),
        headers=await auth_headers(other_user),
    )

    assert response.status_code == 404


async def test_get_workload_not_found(
    client: AsyncClient,
    db_session: AsyncSession,
):
    user = await create_user(db_session, "notfound")

    response = await client.get(
        f"/workloads/{uuid4()}",
        headers=await auth_headers(user),
    )

    assert response.status_code == 404


async def test_update_workload_not_found(
    client: AsyncClient,
    db_session: AsyncSession,
):
    user = await create_user(db_session, "update_notfound")

    response = await client.patch(
        f"/workloads/{uuid4()}",
        json={
            "total_requests": 100,
        },
        headers=await auth_headers(user),
    )

    assert response.status_code == 404


async def test_delete_workload_not_found(
    client: AsyncClient,
    db_session: AsyncSession,
):
    user = await create_user(db_session, "delete_notfound")

    response = await client.delete(
        f"/workloads/{uuid4()}",
        headers=await auth_headers(user),
    )

    assert response.status_code == 404


async def test_unauthenticated_workload_request(
    client: AsyncClient,
):
    response = await client.get("/workloads/")

    assert response.status_code == 401