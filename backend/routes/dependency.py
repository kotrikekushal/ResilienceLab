from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from backend.db.models.dependency import DependencyDB
from backend.db.models.service import ServiceDB
from backend.db.models.system import SystemDB
from backend.db.models.user import UserDB
from backend.db.session import get_db
from backend.models.dependency import (
    DependencyCreate,
    DependencyResponse,
    DependencyUpdate,
)
from backend.security.dependencies import get_current_user


router = APIRouter(
    prefix="/dependencies",
    tags=["Dependencies"],
)


async def get_owned_dependency(
    db: AsyncSession,
    dependency_id: UUID,
    user_id: UUID,
) -> DependencyDB:
    source_service = aliased(ServiceDB)
    target_service = aliased(ServiceDB)

    source_system = aliased(SystemDB)
    target_system = aliased(SystemDB)

    result = await db.execute(
        select(DependencyDB)
        .join(
            source_service,
            DependencyDB.source_service_id == source_service.id,
        )
        .join(
            source_system,
            source_service.system_id == source_system.id,
        )
        .join(
            target_service,
            DependencyDB.target_service_id == target_service.id,
        )
        .join(
            target_system,
            target_service.system_id == target_system.id,
        )
        .where(
            DependencyDB.id == dependency_id,
            source_system.user_id == user_id,
            target_system.user_id == user_id,
        )
    )

    dependency = result.scalar_one_or_none()

    if dependency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dependency not found",
        )

    return dependency


async def verify_owned_service(
    db: AsyncSession,
    service_id: UUID,
    user_id: UUID,
) -> bool:
    result = await db.execute(
        select(ServiceDB)
        .join(
            SystemDB,
            ServiceDB.system_id == SystemDB.id,
        )
        .where(
            ServiceDB.id == service_id,
            SystemDB.user_id == user_id,
        )
    )

    return result.scalar_one_or_none() is not None


@router.post(
    "/",
    response_model=DependencyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dependency(
    data: DependencyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    source_owned = await verify_owned_service(
        db=db,
        service_id=data.source_service_id,
        user_id=current_user.id,
    )

    if not source_owned:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source service not found",
        )

    target_owned = await verify_owned_service(
        db=db,
        service_id=data.target_service_id,
        user_id=current_user.id,
    )

    if not target_owned:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target service not found",
        )

    dependency = DependencyDB(
        source_service_id=data.source_service_id,
        target_service_id=data.target_service_id,
        dependency_type=data.dependency_type,
    )

    db.add(dependency)

    await db.commit()
    await db.refresh(dependency)

    return dependency


@router.get(
    "/",
    response_model=list[DependencyResponse],
)
async def get_dependencies(
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    source_service = aliased(ServiceDB)
    target_service = aliased(ServiceDB)

    source_system = aliased(SystemDB)
    target_system = aliased(SystemDB)

    result = await db.execute(
        select(DependencyDB)
        .join(
            source_service,
            DependencyDB.source_service_id == source_service.id,
        )
        .join(
            source_system,
            source_service.system_id == source_system.id,
        )
        .join(
            target_service,
            DependencyDB.target_service_id == target_service.id,
        )
        .join(
            target_system,
            target_service.system_id == target_system.id,
        )
        .where(
            source_system.user_id == current_user.id,
            target_system.user_id == current_user.id,
        )
    )

    return result.scalars().all()


@router.get(
    "/{dependency_id}",
    response_model=DependencyResponse,
)
async def get_dependency(
    dependency_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    return await get_owned_dependency(
        db=db,
        dependency_id=dependency_id,
        user_id=current_user.id,
    )


@router.patch(
    "/{dependency_id}",
    response_model=DependencyResponse,
)
async def update_dependency(
    dependency_id: UUID,
    data: DependencyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    dependency = await get_owned_dependency(
        db=db,
        dependency_id=dependency_id,
        user_id=current_user.id,
    )

    update_data = data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(dependency, field, value)

    await db.commit()
    await db.refresh(dependency)

    return dependency


@router.delete(
    "/{dependency_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_dependency(
    dependency_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    dependency = await get_owned_dependency(
        db=db,
        dependency_id=dependency_id,
        user_id=current_user.id,
    )

    await db.delete(dependency)

    await db.commit()

    return None