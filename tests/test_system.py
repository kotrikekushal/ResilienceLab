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


@pytest.mark.asyncio
async def test_create_system(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.post(
            "/systems/",
            json={
                "name": "Test System",
                "description": "System for pytest",
            },
        )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Test System"
    assert data["description"] == "System for pytest"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_get_systems(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        await client.post(
            "/systems/",
            json={
                "name": "System 1",
                "description": "First system",
            },
        )

        await client.post(
            "/systems/",
            json={
                "name": "System 2",
                "description": "Second system",
            },
        )

        response = await client.get("/systems/")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["name"] == "System 1"
    assert data[1]["name"] == "System 2"


@pytest.mark.asyncio
async def test_get_system(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        create_response = await client.post(
            "/systems/",
            json={
                "name": "Get Test System",
                "description": "Testing get",
            },
        )

        system_id = create_response.json()["id"]

        response = await client.get(
            f"/systems/{system_id}"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == system_id
    assert data["name"] == "Get Test System"
    assert data["description"] == "Testing get"


@pytest.mark.asyncio
async def test_get_system_not_found(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get(
            "/systems/00000000-0000-0000-0000-000000000000"
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "System not found"


@pytest.mark.asyncio
async def test_update_system(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        create_response = await client.post(
            "/systems/",
            json={
                "name": "Original Name",
                "description": "Original description",
            },
        )

        system_id = create_response.json()["id"]

        response = await client.patch(
            f"/systems/{system_id}",
            json={
                "name": "Updated Name",
                "description": "Updated description",
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == system_id
    assert data["name"] == "Updated Name"
    assert data["description"] == "Updated description"


@pytest.mark.asyncio
async def test_update_system_not_found(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.patch(
            "/systems/00000000-0000-0000-0000-000000000000",
            json={
                "name": "Updated Name",
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "System not found"


@pytest.mark.asyncio
async def test_delete_system(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        create_response = await client.post(
            "/systems/",
            json={
                "name": "Delete Test System",
                "description": "System to delete",
            },
        )

        system_id = create_response.json()["id"]

        delete_response = await client.delete(
            f"/systems/{system_id}"
        )

        get_response = await client.get(
            f"/systems/{system_id}"
        )

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_system_not_found(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.delete(
            "/systems/00000000-0000-0000-0000-000000000000"
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "System not found"