from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.service import ServiceDB
from backend.db.session import get_db
from backend.models.service import (
    ServiceCreate,
    ServiceResponse,
    ServiceUpdate,
)


router = APIRouter(
    prefix="/services",
    tags=["Services"],
)


@router.post(
    "/",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_service(
    data: ServiceCreate,
    db: AsyncSession = Depends(get_db),
):
    service = ServiceDB(
        system_id=data.system_id,
        name=data.name,
        description=data.description,
        base_url=data.base_url,
        docker_container_name=getattr(
            data,
            "docker_container_name",
            None,
        ),
    )

    db.add(service)

    await db.commit()
    await db.refresh(service)

    return service


@router.get(
    "/",
    response_model=list[ServiceResponse],
)
async def get_services(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ServiceDB)
    )

    services = result.scalars().all()

    return services


@router.get(
    "/{service_id}",
    response_model=ServiceResponse,
)
async def get_service(
    service_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ServiceDB).where(
            ServiceDB.id == service_id
        )
    )

    service = result.scalar_one_or_none()

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )

    return service


@router.patch(
    "/{service_id}",
    response_model=ServiceResponse,
)
async def update_service(
    service_id: UUID,
    data: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ServiceDB).where(
            ServiceDB.id == service_id
        )
    )

    service = result.scalar_one_or_none()

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )

    update_data = data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(service, field, value)

    await db.commit()
    await db.refresh(service)

    return service


@router.delete(
    "/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_service(
    service_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ServiceDB).where(
            ServiceDB.id == service_id
        )
    )

    service = result.scalar_one_or_none()

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )

    await db.delete(service)

    await db.commit()