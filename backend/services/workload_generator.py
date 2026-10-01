import asyncio
import time

import httpx


async def generate_workload(
    base_url: str,
    total_requests: int,
    requests_per_second: int,
    duration_seconds: int,
    target_url: str | None = None,
):
    results = []

    interval = 1 / requests_per_second

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=5.0,
            read=30.0,
            write=30.0,
            pool=5.0,
        )
    ) as client:

        experiment_start_time = (
            time.monotonic()
        )

        request_tasks = []

        async def send_request():

            request_start_time = (
                time.monotonic()
            )

            try:

                # ------------------------------------------------
                # REQUEST HEADERS
                # ------------------------------------------------
                #
                # When the application failure proxy is used,
                # tell it the real target service.
                #

                headers = {}

                if target_url is not None:

                    headers[
                        "X-Resilience-Target-URL"
                    ] = target_url

                # ------------------------------------------------
                # SEND REAL REQUEST
                # ------------------------------------------------
                #
                # base_url can be:
                #
                # 1. Real target service
                #
                # OR
                #
                # 2. Application failure proxy
                #
                # The workload generator itself does not inject
                # any failure.
                #

                response = await client.get(
                    base_url,
                    headers=headers,
                )

                return {
                    "status_code": (
                        response.status_code
                    ),
                    "latency": (
                        time.monotonic()
                        - request_start_time
                    ),
                    "success": (
                        response.is_success
                    ),
                }

            except httpx.TimeoutException as e:

                return {
                    "status_code": None,
                    "latency": (
                        time.monotonic()
                        - request_start_time
                    ),
                    "success": False,
                    "error": str(e),
                    "failure_type": "timeout",
                }

            except httpx.ConnectError as e:

                return {
                    "status_code": None,
                    "latency": (
                        time.monotonic()
                        - request_start_time
                    ),
                    "success": False,
                    "error": str(e),
                    "failure_type": "connection_error",
                }

            except httpx.RequestError as e:

                return {
                    "status_code": None,
                    "latency": (
                        time.monotonic()
                        - request_start_time
                    ),
                    "success": False,
                    "error": str(e),
                    "failure_type": type(e).__name__,
                }

            except Exception as e:

                return {
                    "status_code": None,
                    "latency": (
                        time.monotonic()
                        - request_start_time
                    ),
                    "success": False,
                    "error": str(e),
                    "failure_type": type(e).__name__,
                }

        # --------------------------------------------------------
        # GENERATE REQUESTS
        # --------------------------------------------------------

        for request_number in range(
            total_requests
        ):

            elapsed_time = (
                time.monotonic()
                - experiment_start_time
            )

            # Stop creating new requests when
            # experiment duration ends.

            if elapsed_time >= duration_seconds:
                break

            task = asyncio.create_task(
                send_request()
            )

            request_tasks.append(task)

            # ----------------------------------------------------
            # MAINTAIN REQUEST RATE
            # ----------------------------------------------------

            next_request_time = (
                experiment_start_time
                + (
                    request_number + 1
                ) * interval
            )

            sleep_time = (
                next_request_time
                - time.monotonic()
            )

            if sleep_time > 0:

                await asyncio.sleep(
                    sleep_time
                )

        # --------------------------------------------------------
        # WAIT FOR ALL REQUESTS
        # --------------------------------------------------------

        if request_tasks:

            results = await asyncio.gather(
                *request_tasks
            )

    return results