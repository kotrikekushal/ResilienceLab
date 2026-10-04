import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.db.session import get_db
from backend.db.models.user import UserDB
from backend.security.password import hash_password
from backend.security.jwt import create_access_token


@pytest.fixture
def override_db(db_session):
    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db

    yield

    app.dependency_overrides.clear()


async def create_test_user(
    db_session,
    suffix="1",
):
    user = UserDB(
        username=f"dependency_user_{suffix}",
        email=f"dependency_{suffix}@example.com",
        password_hash=hash_password("StrongPassword@123"),
        is_active=True,
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


def auth_headers(user):
    token = create_access_token(user.id)

    return {
        "Authorization": f"Bearer {token}",
    }


async def create_test_services(
    client,
    user,
    system_name="Test System",
    source_name="Source Service",
    target_name="Target Service",
):
    system_response = await client.post(
        "/systems/",
        json={
            "name": system_name,
            "description": "System for dependency tests",
        },
        headers=auth_headers(user),
    )

    assert system_response.status_code == 201

    system_id = system_response.json()["id"]

    source_response = await client.post(
        "/services/",
        json={
            "system_id": system_id,
            "name": source_name,
            "description": "Source service",
            "base_url": "http://source-service:8000",
            "docker_container_name": "source-service",
        },
        headers=auth_headers(user),
    )

    assert source_response.status_code == 201

    source_service_id = source_response.json()["id"]

    target_response = await client.post(
        "/services/",
        json={
            "system_id": system_id,
            "name": target_name,
            "description": "Target service",
            "base_url": "http://target-service:8000",
            "docker_container_name": "target-service",
        },
        headers=auth_headers(user),
    )

    assert target_response.status_code == 201

    target_service_id = target_response.json()["id"]

    return source_service_id, target_service_id


async def create_dependency(
    client,
    source_service_id,
    target_service_id,
    user,
    dependency_type="HTTP",
):
    response = await client.post(
        "/dependencies/",
        json={
            "source_service_id": source_service_id,
            "target_service_id": target_service_id,
            "dependency_type": dependency_type,
        },
        headers=auth_headers(user),
    )

    assert response.status_code == 201

    return response.json()


@pytest.mark.asyncio
async def test_create_dependency(
    db_session,
    override_db,
):
    user = await create_test_user(
        db_session,
        "create",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        source_service_id, target_service_id = (
            await create_test_services(
                client,
                user,
            )
        )

        response = await client.post(
            "/dependencies/",
            json={
                "source_service_id": source_service_id,
                "target_service_id": target_service_id,
                "dependency_type": "HTTP",
            },
            headers=auth_headers(user),
        )

    assert response.status_code == 201

    data = response.json()

    assert "id" in data
    assert data["source_service_id"] == source_service_id
    assert data["target_service_id"] == target_service_id
    assert data["dependency_type"] == "HTTP"
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_dependencies(
    db_session,
    override_db,
):
    user = await create_test_user(
        db_session,
        "list",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        source_service_id, target_service_id = (
            await create_test_services(
                client,
                user,
            )
        )

        await create_dependency(
            client,
            source_service_id,
            target_service_id,
            user,
            "HTTP",
        )

        second_source_id, second_target_id = (
            await create_test_services(
                client,
                user,
                system_name="Second Test System",
                source_name="Second Source",
                target_name="Second Target",
            )
        )

        await create_dependency(
            client,
            second_source_id,
            second_target_id,
            user,
            "DATABASE",
        )

        response = await client.get(
            "/dependencies/",
            headers=auth_headers(user),
        )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    assert data[0]["source_service_id"] == source_service_id
    assert data[0]["target_service_id"] == target_service_id
    assert data[0]["dependency_type"] == "HTTP"

    assert data[1]["source_service_id"] == second_source_id
    assert data[1]["target_service_id"] == second_target_id
    assert data[1]["dependency_type"] == "DATABASE"


@pytest.mark.asyncio
async def test_get_dependency(
    db_session,
    override_db,
):
    user = await create_test_user(
        db_session,
        "get",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        source_service_id, target_service_id = (
            await create_test_services(
                client,
                user,
            )
        )

        data = await create_dependency(
            client,
            source_service_id,
            target_service_id,
            user,
        )

        response = await client.get(
            f"/dependencies/{data['id']}",
            headers=auth_headers(user),
        )

    assert response.status_code == 200

    result = response.json()

    assert result["id"] == data["id"]
    assert result["source_service_id"] == source_service_id
    assert result["target_service_id"] == target_service_id
    assert result["dependency_type"] == "HTTP"


@pytest.mark.asyncio
async def test_get_dependency_not_found(
    db_session,
    override_db,
):
    user = await create_test_user(
        db_session,
        "notfound",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get(
            "/dependencies/00000000-0000-0000-0000-000000000000",
            headers=auth_headers(user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Dependency not found"


@pytest.mark.asyncio
async def test_update_dependency(
    db_session,
    override_db,
):
    user = await create_test_user(
        db_session,
        "update",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        source_service_id, target_service_id = (
            await create_test_services(
                client,
                user,
            )
        )

        data = await create_dependency(
            client,
            source_service_id,
            target_service_id,
            user,
        )

        response = await client.patch(
            f"/dependencies/{data['id']}",
            json={
                "dependency_type": "DATABASE",
            },
            headers=auth_headers(user),
        )

    assert response.status_code == 200

    result = response.json()

    assert result["id"] == data["id"]
    assert result["source_service_id"] == source_service_id
    assert result["target_service_id"] == target_service_id
    assert result["dependency_type"] == "DATABASE"


@pytest.mark.asyncio
async def test_update_dependency_not_found(
    db_session,
    override_db,
):
    user = await create_test_user(
        db_session,
        "updatenotfound",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.patch(
            "/dependencies/00000000-0000-0000-0000-000000000000",
            json={
                "dependency_type": "DATABASE",
            },
            headers=auth_headers(user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Dependency not found"


@pytest.mark.asyncio
async def test_delete_dependency(
    db_session,
    override_db,
):
    user = await create_test_user(
        db_session,
        "delete",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        source_service_id, target_service_id = (
            await create_test_services(
                client,
                user,
            )
        )

        data = await create_dependency(
            client,
            source_service_id,
            target_service_id,
            user,
        )

        delete_response = await client.delete(
            f"/dependencies/{data['id']}",
            headers=auth_headers(user),
        )

        get_response = await client.get(
            f"/dependencies/{data['id']}",
            headers=auth_headers(user),
        )

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_dependency_not_found(
    db_session,
    override_db,
):
    user = await create_test_user(
        db_session,
        "deletenotfound",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.delete(
            "/dependencies/00000000-0000-0000-0000-000000000000",
            headers=auth_headers(user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Dependency not found"


@pytest.mark.asyncio
async def test_unauthenticated_dependency_request(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get(
            "/dependencies/",
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cross_user_dependency_access_denied(
    db_session,
    override_db,
):
    owner = await create_test_user(
        db_session,
        "owner",
    )

    other_user = await create_test_user(
        db_session,
        "other",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        source_service_id, target_service_id = (
            await create_test_services(
                client,
                owner,
                system_name="Owner System",
            )
        )

        data = await create_dependency(
            client,
            source_service_id,
            target_service_id,
            owner,
        )

        response = await client.get(
            f"/dependencies/{data['id']}",
            headers=auth_headers(other_user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Dependency not found"


@pytest.mark.asyncio
async def test_cross_user_dependency_creation_denied(
    db_session,
    override_db,
):
    owner = await create_test_user(
        db_session,
        "createowner",
    )

    other_user = await create_test_user(
        db_session,
        "createother",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        source_service_id, target_service_id = (
            await create_test_services(
                client,
                owner,
                system_name="Owner Dependency System",
            )
        )

        response = await client.post(
            "/dependencies/",
            json={
                "source_service_id": source_service_id,
                "target_service_id": target_service_id,
                "dependency_type": "HTTP",
            },
            headers=auth_headers(other_user),
        )

    assert response.status_code == 404