import time
from types import SimpleNamespace

import pytest

from backend.services.failure_injector import (
    inject_latency,
    inject_error,
    inject_timeout,
    inject_connection_error,
    inject_connection_reset,
    inject_dns_error,
    inject_service_unavailable,
    inject_dependency_error,
    inject_rate_limit,
    inject_server_error,
    apply_failure,
)


@pytest.mark.asyncio
async def test_inject_latency():
    start = time.monotonic()

    await inject_latency(20)

    elapsed = time.monotonic() - start

    assert elapsed >= 0.02


@pytest.mark.asyncio
async def test_inject_error():
    with pytest.raises(
        RuntimeError,
        match="Injected failure",
    ):
        await inject_error()


@pytest.mark.asyncio
async def test_inject_timeout():
    start = time.monotonic()

    with pytest.raises(
        TimeoutError,
        match="Injected timeout",
    ):
        await inject_timeout(20)

    elapsed = time.monotonic() - start

    assert elapsed >= 0.02


@pytest.mark.asyncio
async def test_inject_connection_error():
    with pytest.raises(
        ConnectionError,
        match="Injected connection failure",
    ):
        await inject_connection_error()


@pytest.mark.asyncio
async def test_inject_connection_reset():
    with pytest.raises(
        ConnectionResetError,
        match="Injected connection reset",
    ):
        await inject_connection_reset()


@pytest.mark.asyncio
async def test_inject_dns_error():
    with pytest.raises(
        OSError,
        match="Injected DNS resolution failure",
    ):
        await inject_dns_error()


@pytest.mark.asyncio
async def test_inject_service_unavailable():
    with pytest.raises(
        RuntimeError,
        match="Injected service unavailable",
    ):
        await inject_service_unavailable()


@pytest.mark.asyncio
async def test_inject_dependency_error():
    with pytest.raises(
        RuntimeError,
        match="Injected dependency failure",
    ):
        await inject_dependency_error()


@pytest.mark.asyncio
async def test_inject_rate_limit():
    with pytest.raises(
        RuntimeError,
        match="Injected rate limit",
    ):
        await inject_rate_limit()


@pytest.mark.asyncio
async def test_inject_server_error():
    with pytest.raises(
        RuntimeError,
        match="Injected server error",
    ):
        await inject_server_error()


@pytest.mark.asyncio
async def test_apply_failure_latency():
    failure = SimpleNamespace(
        failure_type="latency",
        parameters={"delay_ms": 20},
    )

    start = time.monotonic()

    await apply_failure(failure)

    elapsed = time.monotonic() - start

    assert elapsed >= 0.02


@pytest.mark.asyncio
async def test_apply_failure_error():
    failure = SimpleNamespace(
        failure_type="error",
        parameters={},
    )

    with pytest.raises(
        RuntimeError,
        match="Injected failure",
    ):
        await apply_failure(failure)


@pytest.mark.asyncio
async def test_apply_failure_timeout():
    failure = SimpleNamespace(
        failure_type="timeout",
        parameters={"timeout_ms": 20},
    )

    with pytest.raises(
        TimeoutError,
        match="Injected timeout",
    ):
        await apply_failure(failure)


@pytest.mark.asyncio
async def test_apply_failure_connection_error():
    failure = SimpleNamespace(
        failure_type="connection_error",
        parameters={},
    )

    with pytest.raises(
        ConnectionError,
        match="Injected connection failure",
    ):
        await apply_failure(failure)


@pytest.mark.asyncio
async def test_apply_failure_connection_reset():
    failure = SimpleNamespace(
        failure_type="connection_reset",
        parameters={},
    )

    with pytest.raises(
        ConnectionResetError,
        match="Injected connection reset",
    ):
        await apply_failure(failure)


@pytest.mark.asyncio
async def test_apply_failure_dns_error():
    failure = SimpleNamespace(
        failure_type="dns_error",
        parameters={},
    )

    with pytest.raises(
        OSError,
        match="Injected DNS resolution failure",
    ):
        await apply_failure(failure)


@pytest.mark.asyncio
async def test_apply_failure_service_unavailable():
    failure = SimpleNamespace(
        failure_type="service_unavailable",
        parameters={},
    )

    with pytest.raises(
        RuntimeError,
        match="Injected service unavailable",
    ):
        await apply_failure(failure)


@pytest.mark.asyncio
async def test_apply_failure_dependency_error():
    failure = SimpleNamespace(
        failure_type="dependency_error",
        parameters={},
    )

    with pytest.raises(
        RuntimeError,
        match="Injected dependency failure",
    ):
        await apply_failure(failure)


@pytest.mark.asyncio
async def test_apply_failure_rate_limit():
    failure = SimpleNamespace(
        failure_type="rate_limit",
        parameters={},
    )

    with pytest.raises(
        RuntimeError,
        match="Injected rate limit",
    ):
        await apply_failure(failure)


@pytest.mark.asyncio
async def test_apply_failure_server_error():
    failure = SimpleNamespace(
        failure_type="server_error",
        parameters={},
    )

    with pytest.raises(
        RuntimeError,
        match="Injected server error",
    ):
        await apply_failure(failure)


@pytest.mark.asyncio
async def test_apply_failure_unsupported_type():
    failure = SimpleNamespace(
        failure_type="unknown_failure",
        parameters={},
    )

    with pytest.raises(
        ValueError,
        match="Unsupported failure type",
    ):
        await apply_failure(failure)