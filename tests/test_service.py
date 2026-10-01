import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.db.session import get_db


@pytest.fixture
def override_db(db_session):
    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db

    yield

    app.dependency_overrides.clear()


async def create_test_system(client):
    response = await client.post(
        "/systems/",
        json={
            "name": "Test System",
            "description": "System for service tests",
        },
    )

    assert response.status_code == 201

    return response.json()["id"]


@pytest.mark.asyncio
async def test_create_service(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        system_id = await create_test_system(client)

        response = await client.post(
            "/services/",
            json={
                "system_id": system_id,
                "name": "Test Service",
                "description": "Service for pytest",
                "base_url": "http://test-service:8000",
                "docker_container_name": "test-service",
            },
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
async def test_get_services(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        system_id = await create_test_system(client)

        await client.post(
            "/services/",
            json={
                "system_id": system_id,
                "name": "Service 1",
                "description": "First service",
                "base_url": "http://service-1:8000",
                "docker_container_name": "service-1",
            },
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
        )

        response = await client.get("/services/")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    assert data[0]["name"] == "Service 1"
    assert data[1]["name"] == "Service 2"

    assert data[0]["system_id"] == system_id
    assert data[1]["system_id"] == system_id


@pytest.mark.asyncio
async def test_get_service(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        system_id = await create_test_system(client)

        create_response = await client.post(
            "/services/",
            json={
                "system_id": system_id,
                "name": "Get Test Service",
                "description": "Testing get service",
                "base_url": "http://get-service:8000",
                "docker_container_name": "get-service",
            },
        )

        assert create_response.status_code == 201

        service_id = create_response.json()["id"]

        response = await client.get(
            f"/services/{service_id}"
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
async def test_get_service_not_found(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get(
            "/services/00000000-0000-0000-0000-000000000000"
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Service not found"


@pytest.mark.asyncio
async def test_update_service(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        system_id = await create_test_system(client)

        create_response = await client.post(
            "/services/",
            json={
                "system_id": system_id,
                "name": "Original Service",
                "description": "Original description",
                "base_url": "http://original-service:8000",
                "docker_container_name": "original-service",
            },
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
async def test_update_service_not_found(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.patch(
            "/services/00000000-0000-0000-0000-000000000000",
            json={
                "name": "Updated Service",
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Service not found"


@pytest.mark.asyncio
async def test_delete_service(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        system_id = await create_test_system(client)

        create_response = await client.post(
            "/services/",
            json={
                "system_id": system_id,
                "name": "Delete Test Service",
                "description": "Service to delete",
                "base_url": "http://delete-service:8000",
                "docker_container_name": "delete-service",
            },
        )

        assert create_response.status_code == 201

        service_id = create_response.json()["id"]

        delete_response = await client.delete(
            f"/services/{service_id}"
        )

        get_response = await client.get(
            f"/services/{service_id}"
        )

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_service_not_found(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.delete(
            "/services/00000000-0000-0000-0000-000000000000"
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Service not found"