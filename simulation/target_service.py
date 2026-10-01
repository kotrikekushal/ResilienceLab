import os

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse


app = FastAPI(title="ResilienceLab Target Service")


DEPENDENCY_URL = os.getenv(
    "DEPENDENCY_URL",
    "http://dependency-service:8003/data",
)


# ------------------------------------------------------------
# HEALTH
# ------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "healthy"
    }


# ------------------------------------------------------------
# MAIN TARGET OPERATION
# ------------------------------------------------------------

@app.get("/")
async def target_operation():

    try:

        async with httpx.AsyncClient(
            timeout=3.0
        ) as client:

            response = await client.get(
                DEPENDENCY_URL
            )

    except httpx.TimeoutException:

        return JSONResponse(
            status_code=502,
            content={
                "error": "Dependency timeout"
            },
        )

    except httpx.RequestError as exc:

        return JSONResponse(
            status_code=502,
            content={
                "error": "Dependency connection failure",
                "detail": str(exc),
            },
        )

    # --------------------------------------------------------
    # DEPENDENCY RETURNED AN ERROR
    # --------------------------------------------------------

    if response.status_code >= 400:

        return JSONResponse(
            status_code=502,
            content={
                "error": "Dependency failure",
                "dependency_status": response.status_code,
            },
        )

    # --------------------------------------------------------
    # DEPENDENCY WORKED
    # --------------------------------------------------------

    return {
        "message": "Target service successful",
        "dependency": response.json(),
    }