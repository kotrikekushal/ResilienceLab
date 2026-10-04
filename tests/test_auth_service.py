import pytest

from backend.models.auth import UserRegister
from backend.services.auth_service import create_user
from backend.models.auth import UserRegister, LoginRequest
from backend.services.auth_service import (
    create_user,
    authenticate_user,
)

@pytest.mark.asyncio
async def test_create_user(db_session):
    user_data = UserRegister(
        username="testuser",
        email="testuser@example.com",
        password="StrongPassword@123",
    )

    user = await create_user(
        db=db_session,
        user_data=user_data,
    )

    assert user.id is not None
    assert user.username == "testuser"
    assert user.email == "testuser@example.com"
    assert user.is_active is True

    assert user.password_hash != "StrongPassword@123"
    assert user.password_hash.startswith("$argon2")


@pytest.mark.asyncio
async def test_create_user_rejects_duplicate_username(db_session):
    first_user = UserRegister(
        username="duplicateuser",
        email="first@example.com",
        password="StrongPassword@123",
    )

    second_user = UserRegister(
        username="duplicateuser",
        email="second@example.com",
        password="StrongPassword@123",
    )

    await create_user(
        db=db_session,
        user_data=first_user,
    )

    with pytest.raises(
        ValueError,
        match="Username or email is already registered",
    ):
        await create_user(
            db=db_session,
            user_data=second_user,
        )


@pytest.mark.asyncio
async def test_create_user_rejects_duplicate_email(db_session):
    first_user = UserRegister(
        username="firstuser",
        email="same@example.com",
        password="StrongPassword@123",
    )

    second_user = UserRegister(
        username="seconduser",
        email="same@example.com",
        password="StrongPassword@123",
    )

    await create_user(
        db=db_session,
        user_data=first_user,
    )

    with pytest.raises(
        ValueError,
        match="Username or email is already registered",
    ):
        await create_user(
            db=db_session,
            user_data=second_user,
        )

@pytest.mark.asyncio
async def test_authenticate_user_with_username(db_session):
    user_data = UserRegister(
        username="loginuser",
        email="login@example.com",
        password="StrongPassword@123",
    )

    await create_user(
        db=db_session,
        user_data=user_data,
    )

    login_data = LoginRequest(
        username="loginuser",
        password="StrongPassword@123",
    )

    user = await authenticate_user(
        db=db_session,
        login_data=login_data,
    )

    assert user.username == "loginuser"
    assert user.email == "login@example.com"


@pytest.mark.asyncio
async def test_authenticate_user_with_email(db_session):
    user_data = UserRegister(
        username="emailuser",
        email="email@example.com",
        password="StrongPassword@123",
    )

    await create_user(
        db=db_session,
        user_data=user_data,
    )

    login_data = LoginRequest(
        username="email@example.com",
        password="StrongPassword@123",
    )

    user = await authenticate_user(
        db=db_session,
        login_data=login_data,
    )

    assert user.username == "emailuser"


@pytest.mark.asyncio
async def test_authenticate_user_rejects_wrong_password(db_session):
    user_data = UserRegister(
        username="wrongpassuser",
        email="wrongpass@example.com",
        password="StrongPassword@123",
    )

    await create_user(
        db=db_session,
        user_data=user_data,
    )

    login_data = LoginRequest(
        username="wrongpassuser",
        password="WrongPassword@123",
    )

    with pytest.raises(
        ValueError,
        match="Invalid username or password",
    ):
        await authenticate_user(
            db=db_session,
            login_data=login_data,
        )


@pytest.mark.asyncio
async def test_authenticate_user_rejects_unknown_user(db_session):
    login_data = LoginRequest(
        username="doesnotexist",
        password="StrongPassword@123",
    )

    with pytest.raises(
        ValueError,
        match="Invalid username or password",
    ):
        await authenticate_user(
            db=db_session,
            login_data=login_data,
        )