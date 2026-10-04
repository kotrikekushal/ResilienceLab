import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.db.session import get_db
from backend.db.models import UserDB
from backend.security.jwt import create_access_token
from backend.security.password import hash_password


@pytest.fixture
def override_db(db_session):
    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db

    yield

    app.dependency_overrides.clear()


async def create_test_user(
    db_session,
    suffix: str,
):
    user = UserDB(
        username=f"service_user_{suffix}",
        email=f"service_{suffix}@example.com",
        password_hash=hash_password(
            "StrongPassword@123"
        ),
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


async def create_test_system(
    client,
    user,
    name="Test System",
):
    response = await client.post(
        "/systems/",
        json={
            "name": name,
            "description": "System for service tests",
        },
        headers=auth_headers(user),
    )

    assert response.status_code == 201

    return response.json()["id"]


@pytest.mark.asyncio
async def test_create_service(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        user = await create_test_user(
            db_session,
            "create",
        )

        system_id = await create_test_system(
            client,
            user,
        )

        response = await client.post(
            "/services/",
            json={
                "system_id": system_id,
                "name": "Test Service",
                "description": "Service for pytest",
                "base_url": "http://test-service:8000",
                "docker_container_name": "test-service",
            },
            headers=auth_headers(user),
        )

    assert response.status_code == 201

    data = response.json()

    assert "id" in data
    assert data["system_id"] == system_id
    assert data["name"] == "Test Service"
    assert data["description"] == "Service for pytest"
    assert data["base_url"] == "http://test-service:8000"
    assert data["docker_container_name"] == "test-service"
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_get_services(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        user = await create_test_user(
            db_session,
            "list",
        )

        system_id = await create_test_system(
            client,
            user,
        )

        await client.post(
            "/services/",
            json={
                "system_id": system_id,
                "name": "Service 1",
                "description": "First service",
                "base_url": "http://service-1:8000",
                "docker_container_name": "service-1",
            },
            headers=auth_headers(user),
        )

        await client.post(
            "/services/",
            json={
                "system_id": system_id,
                "name": "Service 2",
                "description": "Second service",
                "base_url": "http://service-2:8000",
                "docker_container_name": "service-2",
            },
            headers=auth_headers(user),
        )

        response = await client.get(
            "/services/",
            headers=auth_headers(user),
        )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    assert data[0]["name"] == "Service 1"
    assert data[1]["name"] == "Service 2"

    assert data[0]["system_id"] == system_id
    assert data[1]["system_id"] == system_id


@pytest.mark.asyncio
async def test_get_service(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        user = await create_test_user(
            db_session,
            "get",
        )

        system_id = await create_test_system(
            client,
            user,
        )

        create_response = await client.post(
            "/services/",
            json={
                "system_id": system_id,
                "name": "Get Test Service",
                "description": "Testing get service",
                "base_url": "http://get-service:8000",
                "docker_container_name": "get-service",
            },
            headers=auth_headers(user),
        )

        assert create_response.status_code == 201

        service_id = create_response.json()["id"]

        response = await client.get(
            f"/services/{service_id}",
            headers=auth_headers(user),
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == service_id
    assert data["system_id"] == system_id
    assert data["name"] == "Get Test Service"
    assert data["description"] == "Testing get service"
    assert data["base_url"] == "http://get-service:8000"
    assert data["docker_container_name"] == "get-service"


@pytest.mark.asyncio
async def test_get_service_not_found(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        user = await create_test_user(
            db_session,
            "get_not_found",
        )

        response = await client.get(
            "/services/00000000-0000-0000-0000-000000000000",
            headers=auth_headers(user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Service not found"


@pytest.mark.asyncio
async def test_update_service(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        user = await create_test_user(
            db_session,
            "update",
        )

        system_id = await create_test_system(
            client,
            user,
        )

        create_response = await client.post(
            "/services/",
            json={
                "system_id": system_id,
                "name": "Original Service",
                "description": "Original description",
                "base_url": "http://original-service:8000",
                "docker_container_name": "original-service",
            },
            headers=auth_headers(user),
        )

        assert create_response.status_code == 201

        service_id = create_response.json()["id"]

        response = await client.patch(
            f"/services/{service_id}",
            json={
                "name": "Updated Service",
                "description": "Updated description",
                "base_url": "http://updated-service:8000",
                "docker_container_name": "updated-service",
            },
            headers=auth_headers(user),
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == service_id
    assert data["system_id"] == system_id
    assert data["name"] == "Updated Service"
    assert data["description"] == "Updated description"
    assert data["base_url"] == "http://updated-service:8000"
    assert data["docker_container_name"] == "updated-service"


@pytest.mark.asyncio
async def test_update_service_not_found(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        user = await create_test_user(
            db_session,
            "update_not_found",
        )

        response = await client.patch(
            "/services/00000000-0000-0000-0000-000000000000",
            json={
                "name": "Updated Service",
            },
            headers=auth_headers(user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Service not found"


@pytest.mark.asyncio
async def test_delete_service(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        user = await create_test_user(
            db_session,
            "delete",
        )

        system_id = await create_test_system(
            client,
            user,
        )

        create_response = await client.post(
            "/services/",
            json={
                "system_id": system_id,
                "name": "Delete Test Service",
                "description": "Service to delete",
                "base_url": "http://delete-service:8000",
                "docker_container_name": "delete-service",
            },
            headers=auth_headers(user),
        )

        assert create_response.status_code == 201

        service_id = create_response.json()["id"]

        delete_response = await client.delete(
            f"/services/{service_id}",
            headers=auth_headers(user),
        )

        get_response = await client.get(
            f"/services/{service_id}",
            headers=auth_headers(user),
        )

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_service_not_found(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        user = await create_test_user(
            db_session,
            "delete_not_found",
        )

        response = await client.delete(
            "/services/00000000-0000-0000-0000-000000000000",
            headers=auth_headers(user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Service not found"


@pytest.mark.asyncio
async def test_unauthenticated_service_request(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get("/services/")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cross_user_service_access_denied(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        owner = await create_test_user(
            db_session,
            "owner",
        )

        other_user = await create_test_user(
            db_session,
            "other",
        )

        system_id = await create_test_system(
            client,
            owner,
        )

        create_response = await client.post(
            "/services/",
            json={
                "system_id": system_id,
                "name": "Private Service",
                "description": "Owner service",
                "base_url": "http://private-service:8000",
                "docker_container_name": "private-service",
            },
            headers=auth_headers(owner),
        )

        assert create_response.status_code == 201

        service_id = create_response.json()["id"]

        get_response = await client.get(
            f"/services/{service_id}",
            headers=auth_headers(other_user),
        )

        update_response = await client.patch(
            f"/services/{service_id}",
            json={
                "name": "Hacked Service",
            },
            headers=auth_headers(other_user),
        )

        delete_response = await client.delete(
            f"/services/{service_id}",
            headers=auth_headers(other_user),
        )

    assert get_response.status_code == 404
    assert update_response.status_code == 404
    assert delete_response.status_code == 404


@pytest.mark.asyncio
async def test_create_service_for_other_user_system_denied(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        owner = await create_test_user(
            db_session,
            "system_owner",
        )

        other_user = await create_test_user(
            db_session,
            "system_other",
        )

        system_id = await create_test_system(
            client,
            owner,
        )

        response = await client.post(
            "/services/",
            json={
                "system_id": system_id,
                "name": "Unauthorized Service",
                "description": "Should not be created",
                "base_url": "http://unauthorized:8000",
                "docker_container_name": "unauthorized",
            },
            headers=auth_headers(other_user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "System not found"


@pytest.mark.asyncio
async def test_get_services_only_returns_current_user_services(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        owner = await create_test_user(
            db_session,
            "list_owner",
        )

        other_user = await create_test_user(
            db_session,
            "list_other",
        )

        owner_system_id = await create_test_system(
            client,
            owner,
            "Owner System",
        )

        other_system_id = await create_test_system(
            client,
            other_user,
            "Other System",
        )

        owner_service_response = await client.post(
            "/services/",
            json={
                "system_id": owner_system_id,
                "name": "Owner Service",
                "description": "Owner service",
                "base_url": "http://owner-service:8000",
                "docker_container_name": "owner-service",
            },
            headers=auth_headers(owner),
        )

        other_service_response = await client.post(
            "/services/",
            json={
                "system_id": other_system_id,
                "name": "Other Service",
                "description": "Other service",
                "base_url": "http://other-service:8000",
                "docker_container_name": "other-service",
            },
            headers=auth_headers(other_user),
        )

        assert owner_service_response.status_code == 201
        assert other_service_response.status_code == 201

        response = await client.get(
            "/services/",
            headers=auth_headers(owner),
        )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["name"] == "Owner Service"
    assert data[0]["system_id"] == owner_system_id