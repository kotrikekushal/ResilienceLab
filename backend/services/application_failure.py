import asyncio
import socket
import struct
import time
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response


# ============================================================
# FASTAPI CONTROL APPLICATION
# ============================================================

app = FastAPI(
    title="ResilienceLab Application Failure Proxy",
    version="1.0.0",
)


# ============================================================
# SUPPORTED FAILURES
# ============================================================

SUPPORTED_FAILURES = {
    "latency",
    "error",
    "timeout",
    "connection_error",
    "connection_reset",
    "dns_error",
    "service_unavailable",
    "rate_limit",
    "server_error",
}


# ============================================================
# FAILURE CONFIGURATION
# ============================================================


@dataclass
class FailureConfiguration:
    failure_type: str
    duration_seconds: int | None
    parameters: dict
    started_at: float


# ============================================================
# ACTIVE FAILURES
# ============================================================

active_failures: dict[str, list[FailureConfiguration]] = {}


# ============================================================
# FAILURE TYPE HELPERS
# ============================================================


def _validate_parameters(
    failure_type: str,
    parameters: dict,
) -> str | None:
    """
    Validate parameters that are specific to an
    application failure.

    Returns an error message when invalid.
    """

    if not isinstance(parameters, dict):
        return "parameters must be an object"

    if failure_type == "latency":

        delay_ms = parameters.get("delay_ms", 500)

        if not isinstance(delay_ms, (int, float)):
            return "delay_ms must be a number"

        if delay_ms < 0:
            return "delay_ms must not be negative"

    elif failure_type == "timeout":

        timeout_ms = parameters.get("timeout_ms", 5000)

        if not isinstance(timeout_ms, (int, float)):
            return "timeout_ms must be a number"

        if timeout_ms <= 0:
            return "timeout_ms must be greater than 0"

    elif failure_type == "dns_error":

        hostname = parameters.get(
            "hostname",
            "resiliencelab-dns-failure.invalid",
        )

        if not isinstance(hostname, str) or not hostname.strip():
            return "hostname must be a non-empty string"

    elif failure_type in {
        "service_unavailable",
        "rate_limit",
    }:

        retry_after = parameters.get(
            "retry_after_seconds",
            5,
        )

        if not isinstance(retry_after, (int, float)):
            return "retry_after_seconds must be a number"

        if retry_after < 0:
            return "retry_after_seconds must not be negative"

    return None


# ============================================================
# HEALTH CHECK
# ============================================================


@app.get("/health")
async def health():

    return {
        "status": "healthy",
        "service": "application-failure-proxy",
    }


# ============================================================
# CONFIGURE FAILURE
# ============================================================


@app.post("/fault/{service_name}")
async def configure_failure(
    service_name: str,
    request: Request,
):

    data = await request.json()

    failure_type = data.get("failure_type")

    duration_seconds = data.get(
        "duration_seconds"
    )

    parameters = (
        data.get("parameters")
        or {}
    )

    # --------------------------------------------------------
    # VALIDATE FAILURE TYPE
    # --------------------------------------------------------

    if failure_type not in SUPPORTED_FAILURES:

        return JSONResponse(
            status_code=400,
            content={
                "error": "Unsupported application failure",
                "failure_type": failure_type,
            },
        )

    # --------------------------------------------------------
    # VALIDATE DURATION
    # --------------------------------------------------------

    if (
        duration_seconds is not None
        and (
            not isinstance(duration_seconds, (int, float))
            or duration_seconds <= 0
        )
    ):

        return JSONResponse(
            status_code=400,
            content={
                "error": (
                    "duration_seconds must be "
                    "greater than 0"
                )
            },
        )

    # --------------------------------------------------------
    # VALIDATE PARAMETERS
    # --------------------------------------------------------

    parameter_error = _validate_parameters(
        failure_type=failure_type,
        parameters=parameters,
    )

    if parameter_error:

        return JSONResponse(
            status_code=400,
            content={
                "error": parameter_error,
                "failure_type": failure_type,
            },
        )

    # --------------------------------------------------------
    # STORE FAILURE
    # --------------------------------------------------------

    configuration = FailureConfiguration(
        failure_type=failure_type,
        duration_seconds=(
            int(duration_seconds)
            if duration_seconds is not None
            else None
        ),
        parameters=parameters,
        started_at=time.monotonic(),
    )

    active_failures.setdefault(
        service_name,
        [],
    ).append(configuration)

    return {
        "status": "configured",
        "service": service_name,
        "failure_type": failure_type,
        "duration_seconds": duration_seconds,
        "parameters": parameters,
        "active_failure_count": len(active_failures[service_name]),
    }


# ============================================================
# REMOVE FAILURE
# ============================================================


@app.delete("/fault/{service_name}")
async def remove_failure(
    service_name: str,
):

    active_failures.pop(
        service_name,
        None,
    )

    return {
        "status": "removed",
        "service": service_name,
    }


# ============================================================
# GET ACTIVE FAILURE
# ============================================================


@app.get("/fault/{service_name}")
async def get_failure(
    service_name: str,
):

    failures = get_active_failures(service_name)

    if not failures:
        return {
            "active": False,
            "service": service_name,
            "failures": [],
        }

    now = time.monotonic()
    failure_details = []

    for failure in failures:
        remaining = None
        if failure.duration_seconds is not None:
            elapsed = now - failure.started_at
            remaining = max(0.0, failure.duration_seconds - elapsed)

        failure_details.append({
            "failure_type": failure.failure_type,
            "duration_seconds": failure.duration_seconds,
            "remaining_seconds": round(remaining, 3) if remaining is not None else None,
            "parameters": failure.parameters,
        })

    return {
        "active": True,
        "service": service_name,
        "failure_count": len(failures),
        "failures": failure_details,
    }

# ============================================================
# FAILURE EXPIRATION
# ============================================================


def get_active_failures(
    service_name: str,
) -> list[FailureConfiguration]:

    failures = active_failures.get(service_name, [])
    if not failures:
        return []

    now = time.monotonic()
    active: list[FailureConfiguration] = []

    for failure in failures:
        if failure.duration_seconds is None:
            active.append(failure)
            continue

        elapsed = now - failure.started_at
        if elapsed < failure.duration_seconds:
            active.append(failure)

    if active:
        active_failures[service_name] = active
    else:
        active_failures.pop(service_name, None)

    return active

# ============================================================
# REAL HTTP PROXY
# ============================================================


@app.api_route(
    "/proxy/{service_name}/{path:path}",
    methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
        "HEAD",
    ],
)
async def proxy_request(
    service_name: str,
    path: str,
    request: Request,
):

    target_url = request.headers.get(
        "X-Resilience-Target-URL"
    )

    if not target_url:

        return JSONResponse(
            status_code=400,
            content={
                "error": (
                    "X-Resilience-Target-URL "
                    "header is required"
                )
            },
        )

    failures = get_active_failures(service_name)

    if not failures:
        return await forward_request(
            request=request,
            target_url=target_url,
            path=path,
        )

    # Apply every active failure in configuration order.
    # Non-terminal failures such as latency can stack.
    # Terminal failures return/close the request immediately.
    for failure in failures:

        if failure.failure_type == "latency":
            delay_ms = failure.parameters.get("delay_ms", 500)
            await asyncio.sleep(delay_ms / 1000)
            continue

        if failure.failure_type == "error":
            return JSONResponse(status_code=400, content={"error": "Injected application error"})

        if failure.failure_type == "timeout":
            timeout_ms = failure.parameters.get("timeout_ms", 5000)
            await asyncio.sleep(max(timeout_ms / 1000, 31.0))
            return JSONResponse(status_code=504, content={"error": "Injected request timeout"})

        if failure.failure_type == "connection_error":
            return await close_connection(request)

        if failure.failure_type == "connection_reset":
            return await reset_connection(request)

        if failure.failure_type == "dns_error":
            invalid_hostname = failure.parameters.get("hostname", "resiliencelab-dns-failure.invalid")
            try:
                await asyncio.get_running_loop().getaddrinfo(
                    invalid_hostname, 80, type=socket.SOCK_STREAM
                )
            except socket.gaierror as exc:
                return JSONResponse(
                    status_code=502,
                    content={
                        "error": "Upstream DNS resolution failed",
                        "hostname": invalid_hostname,
                        "detail": str(exc),
                    },
                )
            return JSONResponse(
                status_code=502,
                content={
                    "error": "Configured DNS failure hostname resolved unexpectedly",
                    "hostname": invalid_hostname,
                },
            )

        if failure.failure_type == "service_unavailable":
            retry_after = failure.parameters.get("retry_after_seconds", 5)
            return JSONResponse(
                status_code=503,
                content={"error": "Service temporarily unavailable"},
                headers={"Retry-After": str(retry_after)},
            )

        if failure.failure_type == "rate_limit":
            retry_after = failure.parameters.get("retry_after_seconds", 5)
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests"},
                headers={"Retry-After": str(retry_after)},
            )

        if failure.failure_type == "server_error":
            return JSONResponse(status_code=500, content={"error": "Internal server error"})

    return await forward_request(
        request=request,
        target_url=target_url,
        path=path,
    )

# ============================================================
# FORWARD REAL REQUEST TO TARGET
# ============================================================


async def forward_request(
    request: Request,
    target_url: str,
    path: str,
):

    final_url = (
        target_url.rstrip("/")
    )

    if path:

        final_url += (
            "/"
            + path
        )

    if request.url.query:

        final_url += (
            "?"
            + request.url.query
        )

    body = await request.body()

    headers = dict(
        request.headers
    )

    headers.pop(
        "host",
        None,
    )

    headers.pop(
        "X-Resilience-Target-URL",
        None,
    )

    # --------------------------------------------------------
    # REAL UPSTREAM REQUEST
    # --------------------------------------------------------

    timeout = httpx.Timeout(
        connect=5.0,
        read=30.0,
        write=30.0,
        pool=5.0,
    )

    try:

        async with httpx.AsyncClient(
            timeout=timeout
        ) as client:

            response = await client.request(
                method=request.method,
                url=final_url,
                headers=headers,
                content=body,
            )

        response_headers = dict(
            response.headers
        )

        response_headers.pop(
            "content-length",
            None,
        )

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=response_headers,
            media_type=response.headers.get(
                "content-type"
            ),
        )

    except httpx.ConnectError as exc:

        return JSONResponse(
            status_code=502,
            content={
                "error": "Target service connection failed",
                "detail": str(exc),
            },
        )

    except httpx.TimeoutException as exc:

        return JSONResponse(
            status_code=504,
            content={
                "error": "Target service timed out",
                "detail": str(exc),
            },
        )

    except httpx.RequestError as exc:

        return JSONResponse(
            status_code=502,
            content={
                "error": "Target service request failed",
                "detail": str(exc),
            },
        )


# ============================================================
# CLOSE CLIENT CONNECTION
# ============================================================


async def close_connection(
    request: Request,
):

    transport = request.scope.get(
        "transport"
    )

    if transport is not None:

        transport.close()

        # Do not attempt to send an HTTP response after
        # closing the transport.
        return Response(
            status_code=204
        )

    # Some ASGI servers do not expose their transport.
    # In that case a clean HTTP response is the only safe
    # fallback.
    return JSONResponse(
        status_code=503,
        content={
            "error": (
                "Connection could not be closed "
                "at transport level"
            )
        },
    )


# ============================================================
# RESET CLIENT CONNECTION
# ============================================================


async def reset_connection(
    request: Request,
):

    transport = request.scope.get(
        "transport"
    )

    if transport is not None:

        socket_object = (
            transport.get_extra_info(
                "socket"
            )
        )

        if socket_object is not None:

            try:

                # SO_LINGER with zero timeout causes the
                # TCP connection to be terminated using
                # RST instead of a normal FIN close.

                socket_object.setsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_LINGER,
                    struct.pack(
                        "ii",
                        1,
                        0,
                    ),
                )

            except OSError:
                pass

        transport.abort()

        return Response(
            status_code=204
        )

    return JSONResponse(
        status_code=502,
        content={
            "error": (
                "Connection reset could not be "
                "performed at transport level"
            )
        },
    )
