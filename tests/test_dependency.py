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


async def create_test_services(client):
    # Create system
    system_response = await client.post(
        "/systems/",
        json={
            "name": "Test System",
            "description": "System for dependency tests",
        },
    )

    assert system_response.status_code == 201

    system_id = system_response.json()["id"]

    # Create source service
    source_response = await client.post(
        "/services/",
        json={
            "system_id": system_id,
            "name": "Source Service",
            "description": "Source service",
            "base_url": "http://source-service:8000",
            "docker_container_name": "source-service",
        },
    )

    assert source_response.status_code == 201

    source_service_id = source_response.json()["id"]

    # Create target service
    target_response = await client.post(
        "/services/",
        json={
            "system_id": system_id,
            "name": "Target Service",
            "description": "Target service",
            "base_url": "http://target-service:8000",
            "docker_container_name": "target-service",
        },
    )

    assert target_response.status_code == 201

    target_service_id = target_response.json()["id"]

    return source_service_id, target_service_id


@pytest.mark.asyncio
async def test_create_dependency(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        source_service_id, target_service_id = (
            await create_test_services(client)
        )

        response = await client.post(
            "/dependencies/",
            json={
                "source_service_id": source_service_id,
                "target_service_id": target_service_id,
                "dependency_type": "HTTP",
            },
        )

    assert response.status_code == 201

    data = response.json()

    assert "id" in data
    assert data["source_service_id"] == source_service_id
    assert data["target_service_id"] == target_service_id
    assert data["dependency_type"] == "HTTP"
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_dependencies(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        source_service_id, target_service_id = (
            await create_test_services(client)
        )

        # Create first dependency
        response_1 = await client.post(
            "/dependencies/",
            json={
                "source_service_id": source_service_id,
                "target_service_id": target_service_id,
                "dependency_type": "HTTP",
            },
        )

        assert response_1.status_code == 201

        # Create another system and services
        system_response = await client.post(
            "/systems/",
            json={
                "name": "Second Test System",
                "description": "Second system",
            },
        )

        assert system_response.status_code == 201

        system_id = system_response.json()["id"]

        source_response = await client.post(
            "/services/",
            json={
                "system_id": system_id,
                "name": "Second Source",
                "description": "Second source service",
                "base_url": "http://second-source:8000",
                "docker_container_name": "second-source",
            },
        )

        target_response = await client.post(
            "/services/",
            json={
                "system_id": system_id,
                "name": "Second Target",
                "description": "Second target service",
                "base_url": "http://second-target:8000",
                "docker_container_name": "second-target",
            },
        )

        assert source_response.status_code == 201
        assert target_response.status_code == 201

        second_source_id = source_response.json()["id"]
        second_target_id = target_response.json()["id"]

        # Create second dependency
        response_2 = await client.post(
            "/dependencies/",
            json={
                "source_service_id": second_source_id,
                "target_service_id": second_target_id,
                "dependency_type": "DATABASE",
            },
        )

        assert response_2.status_code == 201

        response = await client.get("/dependencies/")

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
async def test_get_dependency(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        source_service_id, target_service_id = (
            await create_test_services(client)
        )

        create_response = await client.post(
            "/dependencies/",
            json={
                "source_service_id": source_service_id,
                "target_service_id": target_service_id,
                "dependency_type": "HTTP",
            },
        )

        assert create_response.status_code == 201

        dependency_id = create_response.json()["id"]

        response = await client.get(
            f"/dependencies/{dependency_id}"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == dependency_id
    assert data["source_service_id"] == source_service_id
    assert data["target_service_id"] == target_service_id
    assert data["dependency_type"] == "HTTP"


@pytest.mark.asyncio
async def test_get_dependency_not_found(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get(
            "/dependencies/00000000-0000-0000-0000-000000000000"
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Dependency not found"


@pytest.mark.asyncio
async def test_update_dependency(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        source_service_id, target_service_id = (
            await create_test_services(client)
        )

        create_response = await client.post(
            "/dependencies/",
            json={
                "source_service_id": source_service_id,
                "target_service_id": target_service_id,
                "dependency_type": "HTTP",
            },
        )

        assert create_response.status_code == 201

        dependency_id = create_response.json()["id"]

        response = await client.patch(
            f"/dependencies/{dependency_id}",
            json={
                "dependency_type": "DATABASE",
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == dependency_id
    assert data["source_service_id"] == source_service_id
    assert data["target_service_id"] == target_service_id
    assert data["dependency_type"] == "DATABASE"


@pytest.mark.asyncio
async def test_update_dependency_not_found(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.patch(
            "/dependencies/00000000-0000-0000-0000-000000000000",
            json={
                "dependency_type": "DATABASE",
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Dependency not found"


@pytest.mark.asyncio
async def test_delete_dependency(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        source_service_id, target_service_id = (
            await create_test_services(client)
        )

        create_response = await client.post(
            "/dependencies/",
            json={
                "source_service_id": source_service_id,
                "target_service_id": target_service_id,
                "dependency_type": "HTTP",
            },
        )

        assert create_response.status_code == 201

        dependency_id = create_response.json()["id"]

        delete_response = await client.delete(
            f"/dependencies/{dependency_id}"
        )

        get_response = await client.get(
            f"/dependencies/{dependency_id}"
        )

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_dependency_not_found(db_session, override_db):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.delete(
            "/dependencies/00000000-0000-0000-0000-000000000000"
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Dependency not found"