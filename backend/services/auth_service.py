from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import UserDB
from backend.models.auth import UserRegister
from backend.security.password import hash_password


async def create_user(
    db: AsyncSession,
    user_data: UserRegister,
) -> UserDB:
    existing_user = await db.execute(
        select(UserDB).where(
            or_(
                UserDB.username == user_data.username,
                UserDB.email == user_data.email,
            )
        )
    )

    if existing_user.scalar_one_or_none() is not None:
        raise ValueError(
            "Username or email is already registered"
        )

    user = UserDB(
        username=user_data.username,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        is_active=True,
    )

    db.add(user)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ValueError(
            "Username or email is already registered"
        )

    await db.refresh(user)

    return user