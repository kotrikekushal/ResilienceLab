import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from .execution import ExecutionDB

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from .experiment import ExperimentDB
    from .service import ServiceDB


class MetricDB(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    latency_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    status_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    success: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    cpu_usage_percent: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    memory_usage_mb: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    request_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    error_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    service: Mapped["ServiceDB"] = relationship(
        back_populates="metrics",
    )

    execution_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey(
        "executions.id",
        ondelete="CASCADE",
    ),
    nullable=False,
    index=True,
)
    execution: Mapped["ExecutionDB"] = relationship(
    back_populates="metrics",
)