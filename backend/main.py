from fastapi import FastAPI
from backend.db.database import create_tables
from backend.routes.system import router as system_router
from backend.routes.service import router as service_router
from backend.routes.dependency import router as dependency_router
from backend.routes.experiment import router as experiment_router
from backend.routes.workload import router as workload_router
from backend.routes.failure import router as failure_router
from backend.routes.metric import router as metric_router
from backend.routes.result import router as result_router
from backend.routes.experiment_run import router as experiment_run_router
from backend.routes.execution import router as execution_router
from backend.routes.auth import router as auth_router

app = FastAPI()

app.include_router(system_router)
app.include_router(service_router)
app.include_router(dependency_router)
app.include_router(experiment_router)
app.include_router(workload_router)
app.include_router(failure_router)
app.include_router(metric_router)
app.include_router(result_router)
app.include_router(experiment_run_router)
app.include_router(execution_router)
app.include_router(auth_router)

@app.on_event("startup")
async def startup():
    await create_tables()