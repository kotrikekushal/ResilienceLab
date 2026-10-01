import pytest_asyncio

from httpx import ASGITransport, AsyncClient

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from backend.config import settings
from backend.db.base import Base
from backend.db.session import get_db
from backend.main import app

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


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        settings.TEST_DATABASE_URL,
        poolclass=NullPool,
    )

    # Safety check: never allow tests to use the production database.
    if settings.TEST_DATABASE_URL == settings.DATABASE_URL:
        await engine.dispose()
        raise RuntimeError(
            "TEST_DATABASE_URL must be different from DATABASE_URL"
        )

    try:
        # Create all tables in the test database.
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        SessionTest = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

        async with SessionTest() as session:
            yield session

    finally:
        # Always clean the test database, even if the test fails.
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)

        await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    