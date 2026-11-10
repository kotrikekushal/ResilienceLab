
import asyncio
import time
from typing import Any

import httpx


async def generate_workload(
    base_url: str,
    total_requests: int,
    requests_per_second: float,
    duration_seconds: int,
    target_url: str | None = None,
    max_concurrency: int = 100,
) -> dict[str, Any]:
    """
    Generate an exact number of requests at a target request rate.

    total_requests:
        Exact number of requests to attempt.

    requests_per_second:
        Target request scheduling rate.

    duration_seconds:
        Expected workload duration, retained for compatibility and
        validation. It does not truncate the exact request count.

    max_concurrency:
        Maximum number of simultaneous HTTP requests.
    """

    if total_requests <= 0:
        raise ValueError("total_requests must be greater than 0")

    if requests_per_second <= 0:
        raise ValueError("requests_per_second must be greater than 0")

    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be greater than 0")

    if max_concurrency <= 0:
        raise ValueError("max_concurrency must be greater than 0")

    interval = 1.0 / float(requests_per_second)
    queue_size = max_concurrency * 2
    request_queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
    results: list[dict[str, Any] | None] = [None] * total_requests

    timeout = httpx.Timeout(
        connect=10.0,
        read=30.0,
        write=30.0,
        pool=30.0,
    )

    limits = httpx.Limits(
        max_connections=max_concurrency,
        max_keepalive_connections=min(max_concurrency, 20),
        keepalive_expiry=30.0,
    )

    workload_start = time.monotonic()

    async def worker(client: httpx.AsyncClient) -> None:
        while True:
            item = await request_queue.get()

            try:
                if item is None:
                    return

                request_number, scheduled_at, enqueued_at = item
                queue_dequeued_at = time.monotonic()
                request_started_at = queue_dequeued_at

                headers = {}
                if target_url:
                    headers["X-Resilience-Target-URL"] = target_url

                result: dict[str, Any] = {
                    "request_number": request_number + 1,
                    "status_code": None,
                    "latency": 0.0,
                    "success": False,
                    "error": None,
                    "failure_type": None,
                    "scheduled_at_offset_seconds": (
                        scheduled_at - workload_start
                    ),
                    "scheduler_lag_seconds": max(
                        0.0, enqueued_at - scheduled_at
                    ),
                    "queue_wait_seconds": max(
                        0.0, queue_dequeued_at - enqueued_at
                    ),
                }

                try:
                    response = await client.get(
                        base_url,
                        headers=headers,
                    )

                    result["status_code"] = response.status_code
                    result["success"] = response.is_success

                    if not response.is_success:
                        result["failure_type"] = "http_error"
                        result["error"] = (
                            f"HTTP {response.status_code}"
                        )

                except httpx.PoolTimeout as exc:
                    result["failure_type"] = "pool_timeout"
                    result["error"] = str(exc)

                except httpx.TimeoutException as exc:
                    result["failure_type"] = "timeout"
                    result["error"] = str(exc)

                except httpx.ConnectError as exc:
                    result["failure_type"] = "connection_error"
                    result["error"] = str(exc)

                except httpx.RequestError as exc:
                    result["failure_type"] = type(exc).__name__
                    result["error"] = str(exc)

                except Exception as exc:
                    result["failure_type"] = type(exc).__name__
                    result["error"] = str(exc)

                finally:
                    result["latency"] = (
                        time.monotonic() - request_started_at
                    )

                results[request_number] = result

            finally:
                request_queue.task_done()

    async with httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        follow_redirects=True,
    ) as client:
        workers = [
            asyncio.create_task(worker(client))
            for _ in range(max_concurrency)
        ]

        try:
            # Schedule every request against an absolute clock.
            # A bounded queue applies backpressure instead of creating
            # an unbounded number of waiting request tasks.
            for request_number in range(total_requests):
                scheduled_at = workload_start + (
                    request_number * interval
                )

                delay = scheduled_at - time.monotonic()
                if delay > 0:
                    await asyncio.sleep(delay)

                await request_queue.put(
                    (request_number, scheduled_at, time.monotonic())
                )

            await request_queue.join()

        finally:
            for _ in workers:
                await request_queue.put(None)

            await asyncio.gather(
                *workers,
                return_exceptions=True,
            )

    workload_end = time.monotonic()
    actual_duration = workload_end - workload_start

    completed_results = [
        result for result in results if result is not None
    ]

    if len(completed_results) != total_requests:
        raise RuntimeError(
            "Workload request accounting error: "
            f"expected {total_requests}, "
            f"completed {len(completed_results)}"
        )

    scheduled_duration = (
        (total_requests - 1) / requests_per_second
        if total_requests > 1
        else 0.0
    )

    return {
        "requests": completed_results,
        "configured_requests": total_requests,
        "attempted_requests": len(completed_results),
        "requests_per_second": float(requests_per_second),
        "configured_duration_seconds": duration_seconds,
        "scheduled_duration_seconds": scheduled_duration,
        "actual_duration_seconds": actual_duration,
        "max_concurrency": max_concurrency,
    }
