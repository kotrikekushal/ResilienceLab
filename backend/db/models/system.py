import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from .service import ServiceDB
    from .dependency import DependencyDB
    from .experiment import ExperimentDB
    from backend.db.models.user import UserDB


class SystemDB(Base):
    __tablename__ = "systems"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        unique=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
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

    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user: Mapped["UserDB"] = relationship(
        "UserDB",
        back_populates="systems",
    )
    # -----------------------------------------
    # Services
    # -----------------------------------------

    services: Mapped[list["ServiceDB"]] = relationship(
        back_populates="system",
        cascade="all, delete-orphan",
    )

    # -----------------------------------------
    # Experiments
    # -----------------------------------------

    experiments: Mapped[list["ExperimentDB"]] = relationship(
        back_populates="system",
    )

    # -----------------------------------------
    # Derived dependencies
    # -----------------------------------------
    #
    # Dependencies belong to services, not directly
    # to systems. This property exposes all outgoing
    # dependencies of all services as one system-level
    # collection for API responses.
    # -----------------------------------------

    @property
    def dependencies(self) -> list["DependencyDB"]:
        dependencies: list["DependencyDB"] = []

        for service in self.services:
            dependencies.extend(
                service.outgoing_dependencies
            )

        return dependencies