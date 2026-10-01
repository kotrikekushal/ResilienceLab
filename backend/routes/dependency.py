from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.dependency import DependencyDB
from backend.db.session import get_db
from backend.models.dependency import (
    DependencyCreate,
    DependencyResponse,
    DependencyUpdate,
)


router = APIRouter(
    prefix="/dependencies",
    tags=["Dependencies"],
)


@router.post(
    "/",
    response_model=DependencyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dependency(
    data: DependencyCreate,
    db: AsyncSession = Depends(get_db),
):
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
):
    result = await db.execute(
        select(DependencyDB)
    )

    dependencies = result.scalars().all()

    return dependencies


@router.get(
    "/{dependency_id}",
    response_model=DependencyResponse,
)
async def get_dependency(
    dependency_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DependencyDB).where(
            DependencyDB.id == dependency_id
        )
    )

    dependency = result.scalar_one_or_none()

    if dependency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dependency not found",
        )

    return dependency


@router.patch(
    "/{dependency_id}",
    response_model=DependencyResponse,
)
async def update_dependency(
    dependency_id: UUID,
    data: DependencyUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DependencyDB).where(
            DependencyDB.id == dependency_id
        )
    )

    dependency = result.scalar_one_or_none()

    if dependency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dependency not found",
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
):
    result = await db.execute(
        select(DependencyDB).where(
            DependencyDB.id == dependency_id
        )
    )

    dependency = result.scalar_one_or_none()

    if dependency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dependency not found",
        )

    await db.delete(dependency)

    await db.commit()