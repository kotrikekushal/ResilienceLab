import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import JSON
from backend.db.base import Base

if TYPE_CHECKING:
    from .system import SystemDB
    from .workload import WorkloadDB
    from .failure import FailureDB
    from .execution import ExecutionDB


class ExperimentDB(Base):
    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    system_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "systems.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="created",
        index=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    system: Mapped["SystemDB"] = relationship(
        back_populates="experiments",
    )

    workload: Mapped["WorkloadDB | None"] = relationship(
        back_populates="experiment",
        uselist=False,
        cascade="all, delete-orphan",
    )

    failures: Mapped[list["FailureDB"]] = relationship(
        back_populates="experiment",
        cascade="all, delete-orphan",
    )

    executions: Mapped[list["ExecutionDB"]] = relationship(
        back_populates="experiment",
        cascade="all, delete-orphan",
    )

    hypothesis = mapped_column(
        JSON,
        nullable=True,
)