from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from backend.db.base import Base
from backend.config import settings
from backend.db.models import (
    SystemDB,
    ServiceDB,
    DependencyDB,
    ExperimentDB,
    WorkloadDB,
    FailureDB,
    MetricDB,
    ResultDB,
    ExecutionDB,
)


DATABASE_URL = settings.DATABASE_URL


engine = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool,
)


SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def create_tables():
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all
        )