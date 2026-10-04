import pytest

from backend.models.auth import UserRegister
from backend.services.auth_service import create_user


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