import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from .system import SystemDB
    from .dependency import DependencyDB
    from .failure import FailureDB
    from .metric import MetricDB


class ServiceDB(Base):
    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    system_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("systems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    base_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    docker_container_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # -----------------------------------------
    # System relationship
    # -----------------------------------------

    system: Mapped["SystemDB"] = relationship(
        back_populates="services",
    )

    # -----------------------------------------
    # Dependencies where this service
    # is the source
    # -----------------------------------------

    outgoing_dependencies: Mapped[list["DependencyDB"]] = relationship(
        foreign_keys="DependencyDB.source_service_id",
        back_populates="source_service",
        cascade="all, delete-orphan",
    )

    # -----------------------------------------
    # Dependencies where this service
    # is the target
    # -----------------------------------------

    incoming_dependencies: Mapped[list["DependencyDB"]] = relationship(
        foreign_keys="DependencyDB.target_service_id",
        back_populates="target_service",
        cascade="all, delete-orphan",
    )

    # -----------------------------------------
    # Failures
    # -----------------------------------------

    failures: Mapped[list["FailureDB"]] = relationship(
        back_populates="service",
        cascade="all, delete-orphan",
    )

    # -----------------------------------------
    # Metrics
    # -----------------------------------------

    metrics: Mapped[list["MetricDB"]] = relationship(
        back_populates="service",
        cascade="all, delete-orphan",
    )