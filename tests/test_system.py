import pytest
from uuid import uuid4

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


async def create_test_user(db_session):
    user = UserDB(
        username=f"testuser_{uuid4().hex[:8]}",
        email=f"test_{uuid4().hex[:8]}@example.com",
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
        "Authorization": f"Bearer {token}"
    }


@pytest.mark.asyncio
async def test_create_system(db_session, override_db):
    user = await create_test_user(db_session)

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
            headers=get_auth_headers(user),
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
    user = await create_test_user(db_session)

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
            headers=get_auth_headers(user),
        )

        await client.post(
            "/systems/",
            json={
                "name": "System 2",
                "description": "Second system",
            },
            headers=get_auth_headers(user),
        )

        response = await client.get(
            "/systems/",
            headers=get_auth_headers(user),
        )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["name"] == "System 1"
    assert data[1]["name"] == "System 2"


@pytest.mark.asyncio
async def test_get_system(db_session, override_db):
    user = await create_test_user(db_session)

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
            headers=get_auth_headers(user),
        )

        system_id = create_response.json()["id"]

        response = await client.get(
            f"/systems/{system_id}",
            headers=get_auth_headers(user),
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == system_id
    assert data["name"] == "Get Test System"
    assert data["description"] == "Testing get"


@pytest.mark.asyncio
async def test_get_system_not_found(db_session, override_db):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get(
            "/systems/00000000-0000-0000-0000-000000000000",
            headers=get_auth_headers(user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "System not found"


@pytest.mark.asyncio
async def test_update_system(db_session, override_db):
    user = await create_test_user(db_session)

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
            headers=get_auth_headers(user),
        )

        system_id = create_response.json()["id"]

        response = await client.patch(
            f"/systems/{system_id}",
            json={
                "name": "Updated Name",
                "description": "Updated description",
            },
            headers=get_auth_headers(user),
        )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == system_id
    assert data["name"] == "Updated Name"
    assert data["description"] == "Updated description"


@pytest.mark.asyncio
async def test_update_system_not_found(db_session, override_db):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.patch(
            "/systems/00000000-0000-0000-0000-000000000000",
            json={
                "name": "Updated Name",
            },
            headers=get_auth_headers(user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "System not found"


@pytest.mark.asyncio
async def test_delete_system(db_session, override_db):
    user = await create_test_user(db_session)

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
            headers=get_auth_headers(user),
        )

        system_id = create_response.json()["id"]

        delete_response = await client.delete(
            f"/systems/{system_id}",
            headers=get_auth_headers(user),
        )

        get_response = await client.get(
            f"/systems/{system_id}",
            headers=get_auth_headers(user),
        )

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_system_not_found(db_session, override_db):
    user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.delete(
            "/systems/00000000-0000-0000-0000-000000000000",
            headers=get_auth_headers(user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "System not found"


# ============================================================
# AUTHENTICATION TESTS
# ============================================================


@pytest.mark.asyncio
async def test_system_requires_authentication(
    db_session,
    override_db,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        response = await client.get("/systems/")

    assert response.status_code == 401


# ============================================================
# OWNERSHIP TESTS
# ============================================================


@pytest.mark.asyncio
async def test_user_cannot_access_another_users_system(
    db_session,
    override_db,
):
    owner = await create_test_user(db_session)
    other_user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        create_response = await client.post(
            "/systems/",
            json={
                "name": "Owner System",
                "description": "Owned by first user",
            },
            headers=get_auth_headers(owner),
        )

        system_id = create_response.json()["id"]

        response = await client.get(
            f"/systems/{system_id}",
            headers=get_auth_headers(other_user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "System not found"


@pytest.mark.asyncio
async def test_user_cannot_update_another_users_system(
    db_session,
    override_db,
):
    owner = await create_test_user(db_session)
    other_user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        create_response = await client.post(
            "/systems/",
            json={
                "name": "Owner System",
                "description": "Owned by first user",
            },
            headers=get_auth_headers(owner),
        )

        system_id = create_response.json()["id"]

        response = await client.patch(
            f"/systems/{system_id}",
            json={
                "name": "Hacked System",
            },
            headers=get_auth_headers(other_user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "System not found"


@pytest.mark.asyncio
async def test_user_cannot_delete_another_users_system(
    db_session,
    override_db,
):
    owner = await create_test_user(db_session)
    other_user = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        create_response = await client.post(
            "/systems/",
            json={
                "name": "Owner System",
                "description": "Owned by first user",
            },
            headers=get_auth_headers(owner),
        )

        system_id = create_response.json()["id"]

        response = await client.delete(
            f"/systems/{system_id}",
            headers=get_auth_headers(other_user),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "System not found"


@pytest.mark.asyncio
async def test_get_systems_returns_only_current_users_systems(
    db_session,
    override_db,
):
    user_a = await create_test_user(db_session)
    user_b = await create_test_user(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        await client.post(
            "/systems/",
            json={
                "name": "User A System",
                "description": "System owned by A",
            },
            headers=get_auth_headers(user_a),
        )

        await client.post(
            "/systems/",
            json={
                "name": "User B System",
                "description": "System owned by B",
            },
            headers=get_auth_headers(user_b),
        )

        response = await client.get(
            "/systems/",
            headers=get_auth_headers(user_a),
        )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["name"] == "User A System"