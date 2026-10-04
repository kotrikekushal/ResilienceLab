import jwt
import pytest
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from uuid import uuid4

from backend.config import settings
from backend.db.models import UserDB
from backend.models.auth import UserRegister
from backend.security.dependencies import get_current_user
from backend.security.jwt import create_access_token
from backend.services.auth_service import create_user


@pytest.mark.asyncio
async def test_get_current_user_with_valid_token(db_session):
    user_data = UserRegister(
        username="currentuser",
        email="current@example.com",
        password="StrongPassword@123",
    )

    user = await create_user(
        db=db_session,
        user_data=user_data,
    )

    token = create_access_token(user.id)

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )

    current_user = await get_current_user(
        credentials=credentials,
        db=db_session,
    )

    assert current_user.id == user.id
    assert current_user.username == "currentuser"
    assert current_user.email == "current@example.com"


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_token(db_session):
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="invalid.jwt.token",
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            credentials=credentials,
            db=db_session,
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == (
        "Invalid or expired authentication token"
    )


@pytest.mark.asyncio
async def test_get_current_user_rejects_expired_token(db_session):
    user_id = uuid4()

    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            credentials=credentials,
            db=db_session,
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == (
        "Invalid or expired authentication token"
    )


@pytest.mark.asyncio
async def test_get_current_user_rejects_nonexistent_user(db_session):
    user_id = uuid4()

    token = create_access_token(user_id)

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            credentials=credentials,
            db=db_session,
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "User not found"


@pytest.mark.asyncio
async def test_get_current_user_rejects_inactive_user(db_session):
    user_data = UserRegister(
        username="inactiveuser",
        email="inactive@example.com",
        password="StrongPassword@123",
    )

    user = await create_user(
        db=db_session,
        user_data=user_data,
    )

    user.is_active = False
    await db_session.commit()

    token = create_access_token(user.id)

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            credentials=credentials,
            db=db_session,
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "User account is inactive"