from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.auth import (
    LoginRequest,
    TokenResponse,
    UserRegister,
    UserResponse,
)
from backend.security.jwt import create_access_token
from backend.services.auth_service import (
    authenticate_user,
    create_user,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await create_user(
            db=db,
            user_data=user_data,
        )

        return user

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/login",
    response_model=TokenResponse,
)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await authenticate_user(
            db=db,
            login_data=login_data,
        )

        access_token = create_access_token(
            user.id
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )