from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    ServiceDB,
    SystemDB,
    UserDB,
)
from backend.db.session import get_db
from backend.models.service import (
    ServiceCreate,
    ServiceResponse,
    ServiceUpdate,
)
from backend.security.dependencies import get_current_user


router = APIRouter(
    prefix="/services",
    tags=["Services"],
)


async def get_owned_service(
    db: AsyncSession,
    service_id: UUID,
    user_id: UUID,
) -> ServiceDB:
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

    service = result.scalar_one_or_none()

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )

    return service


@router.post(
    "/",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_service(
    data: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    system_result = await db.execute(
        select(SystemDB).where(
            SystemDB.id == data.system_id,
            SystemDB.user_id == current_user.id,
        )
    )

    system = system_result.scalar_one_or_none()

    if system is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="System not found",
        )

    service = ServiceDB(
        system_id=data.system_id,
        name=data.name,
        description=data.description,
        base_url=data.base_url,
        docker_container_name=data.docker_container_name,
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
    current_user: UserDB = Depends(get_current_user),
):
    result = await db.execute(
        select(ServiceDB)
        .join(
            SystemDB,
            ServiceDB.system_id == SystemDB.id,
        )
        .where(
            SystemDB.user_id == current_user.id,
        )
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
    current_user: UserDB = Depends(get_current_user),
):
    return await get_owned_service(
        db=db,
        service_id=service_id,
        user_id=current_user.id,
    )


@router.patch(
    "/{service_id}",
    response_model=ServiceResponse,
)
async def update_service(
    service_id: UUID,
    data: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    service = await get_owned_service(
        db=db,
        service_id=service_id,
        user_id=current_user.id,
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
    current_user: UserDB = Depends(get_current_user),
):
    service = await get_owned_service(
        db=db,
        service_id=service_id,
        user_id=current_user.id,
    )

    await db.delete(service)

    await db.commit()

    return None