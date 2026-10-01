import asyncio


async def inject_latency(delay_ms: int):
    await asyncio.sleep(delay_ms / 1000)


async def inject_error():
    raise RuntimeError("Injected failure")


async def inject_timeout(timeout_ms: int):
    await asyncio.sleep(timeout_ms / 1000)
    raise TimeoutError("Injected timeout")


async def inject_connection_error():
    raise ConnectionError("Injected connection failure")


async def inject_connection_reset():
    raise ConnectionResetError("Injected connection reset")


async def inject_dns_error():
    raise OSError("Injected DNS resolution failure")


async def inject_service_unavailable():
    raise RuntimeError("Injected service unavailable")


async def inject_dependency_error():
    raise RuntimeError("Injected dependency failure")


async def inject_rate_limit():
    raise RuntimeError("Injected rate limit")


async def inject_server_error():
    raise RuntimeError("Injected server error")


async def apply_failure(failure):
    parameters = failure.parameters or {}

    if failure.failure_type == "latency":
        delay_ms = parameters.get("delay_ms", 0)
        await inject_latency(delay_ms)

    elif failure.failure_type == "error":
        await inject_error()

    elif failure.failure_type == "timeout":
        timeout_ms = parameters.get("timeout_ms", 1000)
        await inject_timeout(timeout_ms)

    elif failure.failure_type == "connection_error":
        await inject_connection_error()

    elif failure.failure_type == "connection_reset":
        await inject_connection_reset()

    elif failure.failure_type == "dns_error":
        await inject_dns_error()

    elif failure.failure_type == "service_unavailable":
        await inject_service_unavailable()

    elif failure.failure_type == "dependency_error":
        await inject_dependency_error()

    elif failure.failure_type == "rate_limit":
        await inject_rate_limit()

    elif failure.failure_type == "server_error":
        await inject_server_error()

    else:
        raise ValueError(
            f"Unsupported failure type: {failure.failure_type}"
        )