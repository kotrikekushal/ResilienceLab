import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


app = FastAPI(title="ResilienceLab Dependency Service")


# ------------------------------------------------------------
# FAILURE STATE
# ------------------------------------------------------------

failure_active_until = 0.0


class FaultRequest(BaseModel):
    duration_seconds: int = Field(gt=0)


def dependency_failure_active() -> bool:
    global failure_active_until

    if failure_active_until == 0:
        return False

    if time.monotonic() >= failure_active_until:
        failure_active_until = 0
        return False

    return True


# ------------------------------------------------------------
# HEALTH
# ------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "healthy"
    }


# ------------------------------------------------------------
# REAL DEPENDENCY OPERATION
# ------------------------------------------------------------

@app.get("/data")
async def get_data():

    # The dependency itself is failing here.
    if dependency_failure_active():

        return JSONResponse(
            status_code=503,
            content={
                "error": "Dependency service unavailable"
            },
        )

    return {
        "message": "Dependency response successful"
    }


# ------------------------------------------------------------
# ENABLE DEPENDENCY FAILURE
# ------------------------------------------------------------

@app.post("/fault")
async def enable_fault(request: FaultRequest):

    global failure_active_until

    failure_active_until = (
        time.monotonic() + request.duration_seconds
    )

    return {
        "message": "Dependency failure activated",
        "duration_seconds": request.duration_seconds,
    }


# ------------------------------------------------------------
# DISABLE DEPENDENCY FAILURE
# ------------------------------------------------------------

@app.delete("/fault")
async def disable_fault():

    global failure_active_until

    failure_active_until = 0

    return {
        "message": "Dependency failure removed"
    }