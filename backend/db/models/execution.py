import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from .experiment import ExperimentDB
    from .metric import MetricDB
    from .result import ResultDB


class ExecutionDB(Base):
    __tablename__ = "executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "experiments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    run_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    run_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="created",
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

    experiment: Mapped["ExperimentDB"] = relationship(
        back_populates="executions",
    )

    metrics: Mapped[list["MetricDB"]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
    )

    result: Mapped["ResultDB | None"] = relationship(
        back_populates="execution",
        uselist=False,
        cascade="all, delete-orphan",
    )