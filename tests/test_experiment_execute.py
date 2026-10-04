from types import SimpleNamespace

from uuid import uuid4



import pytest



from backend.db.models.system import SystemDB
from backend.db.models.user import UserDB
from backend.security.password import hash_password

from backend.db.models.service import ServiceDB

from backend.db.models.experiment import ExperimentDB

from backend.db.models.workload import WorkloadDB

from sqlalchemy import select

from backend.db.models.metric import MetricDB



import backend.services.experiment_execute as experiment_execute





async def fake_generate_workload(

    base_url,

    total_requests,

    requests_per_second,

    duration_seconds,

    target_url=None,

):

    return [

        {

            "status_code": 200,

            "latency": 0.01,

            "success": True,

        }

        for _ in range(total_requests)

    ]





async def fake_start_multiple_failures(

    failures,

    services,

    default_duration_seconds,

):

    return {

        "started": True,

        "failures": list(failures),

    }





async def fake_stop_multiple_failures(

    failure_context,

):

    return None





async def fake_measure_recovery_time(

    services,

    baseline_services,

    timeout_seconds=30.0,

    probe_interval_seconds=0.25,

    consecutive_healthy_probes=3,

):

    return 0.123





async def create_experiment(

    db,

    total_requests=3,

    requests_per_second=3,

    duration_seconds=1,

):

    user = UserDB(

        username=f"testuser_{uuid4().hex[:8]}",

        email=f"test_{uuid4().hex[:8]}@example.com",

        password_hash=hash_password("TestPassword@123"),

        is_active=True,

    )



    db.add(user)

    await db.flush()



    system = SystemDB(

        name=f"Test System {uuid4()}",

        description="Execution test system",

        user_id=user.id,

    )



    db.add(system)

    await db.flush()



    service = ServiceDB(

        system_id=system.id,

        name=f"Test Service {uuid4()}",

        description="Execution test service",

        base_url="http://test-service",

        docker_container_name="target-service",

    )



    db.add(service)

    await db.flush()



    experiment = ExperimentDB(

        system_id=system.id,

        name=f"Test Experiment {uuid4()}",

        description="Execution engine test",

        status="created",

    )



    db.add(experiment)

    await db.flush()



    workload = WorkloadDB(

        experiment_id=experiment.id,

        total_requests=total_requests,

        requests_per_second=requests_per_second,

        duration_seconds=duration_seconds,

    )



    db.add(workload)



    await db.commit()



    return experiment, system, service





@pytest.mark.asyncio

async def test_create_execution(db_session):

    experiment, _, _ = await create_experiment(db_session)



    execution = await experiment_execute.create_execution(

        db=db_session,

        experiment_id=experiment.id,

        run_type="baseline",

    )



    assert execution.id is not None

    assert execution.experiment_id == experiment.id

    assert execution.run_number == 1

    assert execution.run_type == "baseline"

    assert execution.status == "created"





@pytest.mark.asyncio

async def test_create_execution_increments_run_number(

    db_session,

):

    experiment, _, _ = await create_experiment(db_session)



    first = await experiment_execute.create_execution(

        db=db_session,

        experiment_id=experiment.id,

        run_type="baseline",

    )



    second = await experiment_execute.create_execution(

        db=db_session,

        experiment_id=experiment.id,

        run_type="failure",

    )



    third = await experiment_execute.create_execution(

        db=db_session,

        experiment_id=experiment.id,

        run_type="recovery",

    )



    assert first.run_number == 1

    assert second.run_number == 2

    assert third.run_number == 3





@pytest.mark.asyncio

async def test_create_execution_starts_at_one_for_new_experiment(

    db_session,

):

    experiment, _, _ = await create_experiment(db_session)



    execution = await experiment_execute.create_execution(

        db=db_session,

        experiment_id=experiment.id,

        run_type="baseline",

    )



    assert execution.run_number == 1





@pytest.mark.asyncio

async def test_check_cancellation_does_not_raise(

    db_session,

):

    experiment, _, _ = await create_experiment(db_session)



    await experiment_execute.check_cancellation(

        db=db_session,

        experiment=experiment,

    )





@pytest.mark.asyncio

async def test_check_cancellation_raises_when_requested(

    db_session,

):

    experiment, _, _ = await create_experiment(db_session)



    experiment.status = "cancel_requested"

    await db_session.commit()



    with pytest.raises(

        BaseException,

        match="Experiment cancellation requested",

    ):

        await experiment_execute.check_cancellation(

            db=db_session,

            experiment=experiment,

        )





@pytest.mark.asyncio

async def test_run_experiment_creates_metrics_and_result(

    db_session,

    monkeypatch,

):

    experiment, _, service = await create_experiment(

        db_session,

        total_requests=3,

    )



    monkeypatch.setattr(

        experiment_execute,

        "generate_workload",

        fake_generate_workload,

    )



    execution = await experiment_execute.create_execution(

        db=db_session,

        experiment_id=experiment.id,

        run_type="baseline",

    )



    output = await experiment_execute._run_experiment(

        db=db_session,

        experiment_id=experiment.id,

        execution=execution,

        apply_failures=False,

    )



    assert output["execution"].id == execution.id

    assert output["result"].execution_id == execution.id



    assert output["result"].total_requests == 3

    assert output["result"].successful_requests == 3

    assert output["result"].failed_requests == 0



    assert output["result"].success_rate == 100

    assert output["result"].error_rate == 0

    assert output["result"].availability == 100



    assert len(output["services"]) == 1

    assert output["services"][0]["service_id"] == service.id

    assert output["services"][0]["total_requests"] == 3





@pytest.mark.asyncio

async def test_run_experiment_stores_metrics(

    db_session,

    monkeypatch,

):

    experiment, _, service = await create_experiment(

        db_session,

        total_requests=3,

    )



    monkeypatch.setattr(

        experiment_execute,

        "generate_workload",

        fake_generate_workload,

    )



    execution = await experiment_execute.create_execution(

        db=db_session,

        experiment_id=experiment.id,

        run_type="baseline",

    )



    await experiment_execute._run_experiment(

        db=db_session,

        experiment_id=experiment.id,

        execution=execution,

        apply_failures=False,

    )







    result = await db_session.execute(

        select(MetricDB).where(

            MetricDB.execution_id == execution.id

        )

    )



    metrics = list(result.scalars().all())



    assert len(metrics) == 3



    for metric in metrics:

        assert metric.execution_id == execution.id

        assert metric.service_id == service.id

        assert metric.status_code == 200

        assert metric.success is True

        assert metric.latency_ms == 10





@pytest.mark.asyncio

async def test_run_experiment_validates_missing_workload(

    db_session,

):

    user = UserDB(

        username=f"testuser_{uuid4().hex[:8]}",

        email=f"test_{uuid4().hex[:8]}@example.com",

        password_hash=hash_password("TestPassword@123"),

        is_active=True,

    )



    db_session.add(user)

    await db_session.flush()



    system = SystemDB(

        name=f"System {uuid4()}",

        description="Test",

        user_id=user.id,

    )



    db_session.add(system)

    await db_session.flush()



    service = ServiceDB(

        system_id=system.id,

        name=f"Service {uuid4()}",

        base_url="http://test-service",

        docker_container_name="target-service",

    )



    db_session.add(service)

    await db_session.flush()



    experiment = ExperimentDB(

        system_id=system.id,

        name=f"Experiment {uuid4()}",

        status="created",

    )



    db_session.add(experiment)

    await db_session.commit()



    execution = await experiment_execute.create_execution(

        db=db_session,

        experiment_id=experiment.id,

        run_type="baseline",

    )



    with pytest.raises(

        ValueError,

        match="does not have a workload",

    ):

        await experiment_execute._run_experiment(

            db=db_session,

            experiment_id=experiment.id,

            execution=execution,

            apply_failures=False,

        )





@pytest.mark.asyncio

async def test_execute_experiment_complete_lifecycle(

    db_session,

    monkeypatch,

):

    experiment, _, _ = await create_experiment(

        db_session,

        total_requests=3,

    )



    monkeypatch.setattr(

        experiment_execute,

        "generate_workload",

        fake_generate_workload,

    )



    monkeypatch.setattr(

        experiment_execute,

        "start_multiple_failures",

        fake_start_multiple_failures,

    )



    monkeypatch.setattr(

        experiment_execute,

        "stop_multiple_failures",

        fake_stop_multiple_failures,

    )



    monkeypatch.setattr(

        experiment_execute,

        "measure_recovery_time",

        fake_measure_recovery_time,

    )



    result = await experiment_execute.execute_experiment(

        db=db_session,

        experiment_id=experiment.id,

    )



    assert result["status"] == "completed"

    assert result["experiment_id"] == experiment.id



    executions = result["executions"]



    assert len(executions) == 3



    assert executions[0]["run_number"] == 1

    assert executions[0]["run_type"] == "baseline"

    assert executions[0]["status"] == "completed"



    assert executions[1]["run_number"] == 2

    assert executions[1]["run_type"] == "failure"

    assert executions[1]["status"] == "completed"



    assert executions[2]["run_number"] == 3

    assert executions[2]["run_type"] == "recovery"

    assert executions[2]["status"] == "completed"



    assert result["analysis"] is not None



    await db_session.refresh(experiment)



    assert experiment.status == "completed"

    assert experiment.started_at is not None

    assert experiment.finished_at is not None

    assert experiment.error_message is None





@pytest.mark.asyncio

async def test_execute_experiment_not_found(db_session):

    with pytest.raises(

        ValueError,

        match="Experiment not found",

    ):

        await experiment_execute.execute_experiment(

            db=db_session,

            experiment_id=uuid4(),

        )





@pytest.mark.asyncio

async def test_execute_experiment_already_running(

    db_session,

):

    experiment, _, _ = await create_experiment(db_session)



    experiment.status = "running"

    await db_session.commit()



    with pytest.raises(

        ValueError,

        match="Experiment is already running",

    ):

        await experiment_execute.execute_experiment(

            db=db_session,

            experiment_id=experiment.id,

        )





@pytest.mark.asyncio

async def test_execute_experiment_cancel_requested(

    db_session,

):

    experiment, _, _ = await create_experiment(db_session)



    experiment.status = "cancel_requested"

    await db_session.commit()



    result = await experiment_execute.execute_experiment(

        db=db_session,

        experiment_id=experiment.id,

    )



    assert result["status"] == "cancelled"

    assert result["experiment_id"] == experiment.id

    assert result["executions"] == []

    assert result["analysis"] is None



    await db_session.refresh(experiment)



    assert experiment.status == "cancelled"

    assert experiment.error_message == (

        "Experiment cancelled by user"

    )