import pytest
from datetime import datetime, timezone
from uuid import uuid4

from backend.db.models.system import SystemDB
from backend.db.models.service import ServiceDB
from backend.db.models.experiment import ExperimentDB
from backend.db.models.execution import ExecutionDB
from backend.db.models.metric import MetricDB

from backend.services.execution_service import (
    get_execution_details,
    get_experiment_executions,
    get_execution_metrics,
)


# ============================================================
# GET EXECUTION DETAILS
# ============================================================

@pytest.mark.asyncio
async def test_get_execution_details(db_session):

    system = SystemDB(
        name="Execution Details System",
        description="Test system",
    )

    db_session.add(system)
    await db_session.commit()
    await db_session.refresh(system)

    experiment = ExperimentDB(
        system_id=system.id,
        name="Execution Details Test",
        description="Test experiment",
        status="created",
    )

    db_session.add(experiment)
    await db_session.commit()
    await db_session.refresh(experiment)

    execution = ExecutionDB(
        experiment_id=experiment.id,
        run_number=1,
        run_type="baseline",
        status="completed",
    )

    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(execution)

    result = await get_execution_details(
        db_session,
        execution.id,
    )

    assert result.id == execution.id
    assert result.experiment_id == experiment.id
    assert result.run_number == 1
    assert result.run_type == "baseline"
    assert result.status == "completed"


# ============================================================
# GET EXECUTION DETAILS - NOT FOUND
# ============================================================

@pytest.mark.asyncio
async def test_get_execution_details_not_found(db_session):

    execution_id = uuid4()

    with pytest.raises(
        ValueError,
        match="Execution not found",
    ):
        await get_execution_details(
            db_session,
            execution_id,
        )


# ============================================================
# GET EXPERIMENT EXECUTIONS
# ============================================================

@pytest.mark.asyncio
async def test_get_experiment_executions(db_session):

    system = SystemDB(
        name="Execution History System",
        description="Test system",
    )

    db_session.add(system)
    await db_session.commit()
    await db_session.refresh(system)

    experiment = ExperimentDB(
        system_id=system.id,
        name="Execution History Test",
        description="Test experiment",
        status="created",
    )

    db_session.add(experiment)
    await db_session.commit()
    await db_session.refresh(experiment)

    execution_1 = ExecutionDB(
        experiment_id=experiment.id,
        run_number=1,
        run_type="baseline",
        status="completed",
    )

    execution_2 = ExecutionDB(
        experiment_id=experiment.id,
        run_number=2,
        run_type="failure",
        status="completed",
    )

    db_session.add_all([
        execution_1,
        execution_2,
    ])

    await db_session.commit()

    executions = await get_experiment_executions(
        db_session,
        experiment.id,
    )

    assert len(executions) == 2
    assert executions[0].run_number == 1
    assert executions[1].run_number == 2


# ============================================================
# GET EXPERIMENT EXECUTIONS - ORDER BY RUN NUMBER
# ============================================================

@pytest.mark.asyncio
async def test_get_experiment_executions_ordered_by_run_number(
    db_session,
):

    system = SystemDB(
        name="Execution Order System",
        description="Test system",
    )

    db_session.add(system)
    await db_session.commit()
    await db_session.refresh(system)

    experiment = ExperimentDB(
        system_id=system.id,
        name="Execution Order Test",
        description="Test experiment",
        status="created",
    )

    db_session.add(experiment)
    await db_session.commit()
    await db_session.refresh(experiment)

    execution_3 = ExecutionDB(
        experiment_id=experiment.id,
        run_number=3,
        run_type="recovery",
        status="completed",
    )

    execution_1 = ExecutionDB(
        experiment_id=experiment.id,
        run_number=1,
        run_type="baseline",
        status="completed",
    )

    execution_2 = ExecutionDB(
        experiment_id=experiment.id,
        run_number=2,
        run_type="failure",
        status="completed",
    )

    db_session.add_all([
        execution_3,
        execution_1,
        execution_2,
    ])

    await db_session.commit()

    executions = await get_experiment_executions(
        db_session,
        experiment.id,
    )

    assert [
        execution.run_number
        for execution in executions
    ] == [1, 2, 3]


# ============================================================
# GET EXPERIMENT EXECUTIONS - EMPTY
# ============================================================

@pytest.mark.asyncio
async def test_get_experiment_executions_empty(db_session):

    system = SystemDB(
        name="Empty Execution System",
        description="Test system",
    )

    db_session.add(system)
    await db_session.commit()
    await db_session.refresh(system)

    experiment = ExperimentDB(
        system_id=system.id,
        name="Empty Execution Test",
        description="Test experiment",
        status="created",
    )

    db_session.add(experiment)
    await db_session.commit()
    await db_session.refresh(experiment)

    executions = await get_experiment_executions(
        db_session,
        experiment.id,
    )

    assert executions == []


# ============================================================
# GET EXECUTION METRICS
# ============================================================

@pytest.mark.asyncio
async def test_get_execution_metrics(db_session):

    system = SystemDB(
        name="Metrics System",
        description="Test system",
    )

    db_session.add(system)
    await db_session.commit()
    await db_session.refresh(system)

    # MetricDB requires a service_id,
    # so create the service belonging to this system.
    service = ServiceDB(
        system_id=system.id,
        name="Metrics Service",
        description="Test service",
        base_url="http://localhost:8001",
        docker_container_name="target-service",
    )

    db_session.add(service)
    await db_session.commit()
    await db_session.refresh(service)

    experiment = ExperimentDB(
        system_id=system.id,
        name="Metrics Test",
        description="Test experiment",
        status="created",
    )

    db_session.add(experiment)
    await db_session.commit()
    await db_session.refresh(experiment)

    execution = ExecutionDB(
        experiment_id=experiment.id,
        run_number=1,
        run_type="baseline",
        status="completed",
    )

    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(execution)

    metric_1 = MetricDB(
        execution_id=execution.id,
        service_id=service.id,
        timestamp=datetime.now(timezone.utc),
        latency_ms=100.0,
        status_code=200,
        success=True,
        cpu_usage_percent=20.0,
        memory_usage_mb=100.0,
        request_count=1,
        error_count=0,
    )

    metric_2 = MetricDB(
        execution_id=execution.id,
        service_id=service.id,
        timestamp=datetime.now(timezone.utc),
        latency_ms=120.0,
        status_code=200,
        success=True,
        cpu_usage_percent=25.0,
        memory_usage_mb=110.0,
        request_count=1,
        error_count=0,
    )

    db_session.add_all([
        metric_1,
        metric_2,
    ])

    await db_session.commit()

    metrics = await get_execution_metrics(
        db_session,
        execution.id,
    )

    assert len(metrics) == 2

    assert all(
        metric.execution_id == execution.id
        for metric in metrics
    )

    assert all(
        metric.service_id == service.id
        for metric in metrics
    )


# ============================================================
# GET EXECUTION METRICS - EMPTY
# ============================================================

@pytest.mark.asyncio
async def test_get_execution_metrics_empty(db_session):

    system = SystemDB(
        name="Empty Metrics System",
        description="Test system",
    )

    db_session.add(system)
    await db_session.commit()
    await db_session.refresh(system)

    experiment = ExperimentDB(
        system_id=system.id,
        name="Empty Metrics Test",
        description="Test experiment",
        status="created",
    )

    db_session.add(experiment)
    await db_session.commit()
    await db_session.refresh(experiment)

    execution = ExecutionDB(
        experiment_id=experiment.id,
        run_number=1,
        run_type="baseline",
        status="completed",
    )

    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(execution)

    metrics = await get_execution_metrics(
        db_session,
        execution.id,
    )

    assert metrics == []