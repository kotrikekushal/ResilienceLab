import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from .experiment import ExperimentDB
    from .execution import ExecutionDB


class ResultDB(Base):
    __tablename__ = "results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
        "executions.id",
        ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    total_requests: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    successful_requests: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    failed_requests: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    success_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    error_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    average_latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    p50_latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    p95_latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    p99_latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    throughput: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    availability: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    execution: Mapped["ExecutionDB"] = relationship(
        back_populates="result",
    )