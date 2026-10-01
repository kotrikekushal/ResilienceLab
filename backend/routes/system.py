from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.system import SystemDB
from backend.db.session import get_db
from backend.models.system import (
    SystemCreate,
    SystemResponse,
    SystemUpdate,
)

router = APIRouter(
    prefix="/systems",
    tags=["Systems"],
)


@router.post(
    "/",
    response_model=SystemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_system(
    data: SystemCreate,
    db: AsyncSession = Depends(get_db),
):
    system = SystemDB(
        name=data.name,
        description=data.description,
    )

    db.add(system)
    await db.commit()
    await db.refresh(system)

    return system


@router.get(
    "/",
    response_model=list[SystemResponse],
)
async def get_systems(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SystemDB)
    )

    systems = result.scalars().all()

    return systems


@router.get(
    "/{system_id}",
    response_model=SystemResponse,
)
async def get_system(
    system_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SystemDB).where(SystemDB.id == system_id)
    )

    system = result.scalar_one_or_none()

    if system is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="System not found",
        )

    return system


@router.patch(
    "/{system_id}",
    response_model=SystemResponse,
)
async def update_system(
    system_id: UUID,
    data: SystemUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SystemDB).where(SystemDB.id == system_id)
    )

    system = result.scalar_one_or_none()

    if system is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="System not found",
        )

    update_data = data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(system, field, value)

    await db.commit()
    await db.refresh(system)

    return system


@router.delete(
    "/{system_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_system(
    system_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SystemDB).where(SystemDB.id == system_id)
    )

    system = result.scalar_one_or_none()

    if system is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="System not found",
        )

    await db.delete(system)
    await db.commit()