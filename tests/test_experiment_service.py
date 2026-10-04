import pytest

from uuid import uuid4



from backend.db.models.system import SystemDB
from backend.db.models.user import UserDB
from backend.security.password import hash_password

from backend.db.models.service import ServiceDB

from backend.db.models.dependency import DependencyDB

from backend.db.models.experiment import ExperimentDB

from backend.db.models.workload import WorkloadDB

from backend.db.models.failure import FailureDB



from backend.services.experiment_service import (

    clone_experiment,

    reuse_experiment,

    get_experiment_configuration,

)





# ============================================================

# HELPER

# ============================================================



async def create_source_experiment(db_session):

    """

    Create a complete experiment configuration:



    System

        ├── Service 1

        ├── Service 2

        │

        └── Dependency



    Experiment

        ├── Workload

        └── Failure

    """



    # --------------------------------------------------------

    # SYSTEM

    # --------------------------------------------------------



    user = UserDB(

        username=f"testuser_{uuid4().hex[:8]}",

        email=f"test_{uuid4().hex[:8]}@example.com",

        password_hash=hash_password("TestPassword@123"),

        is_active=True,

    )



    db_session.add(user)

    await db_session.flush()



    system = SystemDB(

        name="Service Test System",

        description="System for experiment service tests",

        user_id=user.id,

    )



    db_session.add(system)

    await db_session.commit()

    await db_session.refresh(system)



    # --------------------------------------------------------

    # SERVICES

    # --------------------------------------------------------



    source_service = ServiceDB(

        system_id=system.id,

        name="Source Service",

        description="Source service",

        base_url="http://source-service:8001",

        docker_container_name="source-service",

    )



    target_service = ServiceDB(

        system_id=system.id,

        name="Target Service",

        description="Target service",

        base_url="http://target-service:8001",

        docker_container_name="target-service",

    )



    db_session.add_all([

        source_service,

        target_service,

    ])



    await db_session.commit()



    await db_session.refresh(source_service)

    await db_session.refresh(target_service)



    # --------------------------------------------------------

    # DEPENDENCY

    # --------------------------------------------------------



    dependency = DependencyDB(

        source_service_id=source_service.id,

        target_service_id=target_service.id,

        dependency_type="http",

    )



    db_session.add(dependency)

    await db_session.commit()

    await db_session.refresh(dependency)



    # --------------------------------------------------------

    # EXPERIMENT

    # --------------------------------------------------------



    experiment = ExperimentDB(

        system_id=system.id,

        name="Original Experiment",

        description="Original experiment description",

        status="created",

        started_at=None,

        finished_at=None,

        error_message=None,

    )



    db_session.add(experiment)

    await db_session.commit()

    await db_session.refresh(experiment)



    # --------------------------------------------------------

    # WORKLOAD

    # --------------------------------------------------------



    workload = WorkloadDB(

        experiment_id=experiment.id,

        total_requests=100,

        requests_per_second=10,

        duration_seconds=10,

    )



    db_session.add(workload)



    # --------------------------------------------------------

    # FAILURE

    # --------------------------------------------------------



    failure = FailureDB(

        experiment_id=experiment.id,

        service_id=target_service.id,

        failure_type="latency",

        duration_seconds=5,

        parameters={

            "delay_ms": 500,

        },

    )



    db_session.add(failure)



    await db_session.commit()



    return {

        "system": system,

        "source_service": source_service,

        "target_service": target_service,

        "dependency": dependency,

        "experiment": experiment,

    }





# ============================================================

# CLONE EXPERIMENT

# ============================================================



@pytest.mark.asyncio

async def test_clone_experiment(db_session):



    data = await create_source_experiment(

        db_session

    )



    source_experiment = data["experiment"]

    system = data["system"]

    target_service = data["target_service"]



    cloned = await clone_experiment(

        db=db_session,

        experiment_id=source_experiment.id,

    )



    # --------------------------------------------------------

    # NEW EXPERIMENT

    # --------------------------------------------------------



    assert cloned.id != source_experiment.id



    assert cloned.name == (

        "Original Experiment (Clone)"

    )



    assert cloned.description == (

        "Original experiment description"

    )



    assert cloned.status == "created"



    # --------------------------------------------------------

    # SYSTEM IS REUSED

    # --------------------------------------------------------



    assert cloned.system_id == system.id



    assert cloned.system.id == system.id



    # --------------------------------------------------------

    # WORKLOAD IS COPIED

    # --------------------------------------------------------



    assert cloned.workload is not None



    assert cloned.workload.id != (

        source_experiment.workload.id

    )



    assert cloned.workload.total_requests == 100



    assert (

        cloned.workload.requests_per_second

        == 10

    )



    assert cloned.workload.duration_seconds == 10



    # --------------------------------------------------------

    # FAILURE IS COPIED

    # --------------------------------------------------------



    assert len(cloned.failures) == 1



    cloned_failure = cloned.failures[0]



    assert (

        cloned_failure.service_id

        == target_service.id

    )



    assert (

        cloned_failure.failure_type

        == "latency"

    )



    assert (

        cloned_failure.duration_seconds

        == 5

    )



    assert cloned_failure.parameters == {

        "delay_ms": 500

    }



    # --------------------------------------------------------

    # FAILURE IS A NEW RECORD

    # --------------------------------------------------------



    assert (

        cloned_failure.id

        != source_experiment.failures[0].id

    )





# ============================================================

# CLONE EXPERIMENT - CUSTOM NAME AND DESCRIPTION

# ============================================================



@pytest.mark.asyncio

async def test_clone_experiment_custom_name_description(

    db_session,

):



    data = await create_source_experiment(

        db_session

    )



    source_experiment = data["experiment"]



    cloned = await clone_experiment(

        db=db_session,

        experiment_id=source_experiment.id,

        new_name="Custom Clone",

        new_description="Custom description",

    )



    assert cloned.name == "Custom Clone"



    assert cloned.description == (

        "Custom description"

    )



    assert cloned.system_id == (

        source_experiment.system_id

    )





# ============================================================

# CLONE EXPERIMENT - NOT FOUND

# ============================================================



@pytest.mark.asyncio

async def test_clone_experiment_not_found(

    db_session,

):



    with pytest.raises(

        ValueError,

        match="Experiment not found",

    ):

        await clone_experiment(

            db=db_session,

            experiment_id=uuid4(),

        )





# ============================================================

# REUSE EXPERIMENT

# ============================================================



@pytest.mark.asyncio

async def test_reuse_experiment(

    db_session,

):



    data = await create_source_experiment(

        db_session

    )



    source_experiment = data["experiment"]

    system = data["system"]



    reused = await reuse_experiment(

        db=db_session,

        experiment_id=source_experiment.id,

    )



    # --------------------------------------------------------

    # NEW EXPERIMENT

    # --------------------------------------------------------



    assert reused.id != source_experiment.id



    assert reused.name == (

        "Original Experiment (Reuse)"

    )



    assert reused.description == (

        "Original experiment description"

    )



    assert reused.status == "created"



    # --------------------------------------------------------

    # SAME SYSTEM

    # --------------------------------------------------------



    assert reused.system_id == system.id



    # --------------------------------------------------------

    # WORKLOAD COPIED

    # --------------------------------------------------------



    assert reused.workload is not None



    assert reused.workload.id != (

        source_experiment.workload.id

    )



    assert reused.workload.total_requests == 100



    assert (

        reused.workload.requests_per_second

        == 10

    )



    assert reused.workload.duration_seconds == 10



    # --------------------------------------------------------

    # FAILURE COPIED

    # --------------------------------------------------------



    assert len(reused.failures) == 1



    assert (

        reused.failures[0].failure_type

        == "latency"

    )





# ============================================================

# REUSE EXPERIMENT - WORKLOAD OVERRIDE

# ============================================================



@pytest.mark.asyncio

async def test_reuse_experiment_workload_override(

    db_session,

):



    data = await create_source_experiment(

        db_session

    )



    source_experiment = data["experiment"]



    reused = await reuse_experiment(

        db=db_session,

        experiment_id=source_experiment.id,

        workload_overrides={

            "total_requests": 500,

            "requests_per_second": 50,

            "duration_seconds": 20,

        },

    )



    assert reused.workload is not None



    assert (

        reused.workload.total_requests

        == 500

    )



    assert (

        reused.workload.requests_per_second

        == 50

    )



    assert (

        reused.workload.duration_seconds

        == 20

    )



    # Original must remain unchanged.



    assert (

        source_experiment.workload.total_requests

        == 100

    )



    assert (

        source_experiment.workload.requests_per_second

        == 10

    )



    assert (

        source_experiment.workload.duration_seconds

        == 10

    )





# ============================================================

# REUSE EXPERIMENT - FAILURE OVERRIDE

# ============================================================



@pytest.mark.asyncio

async def test_reuse_experiment_failure_override(

    db_session,

):



    data = await create_source_experiment(

        db_session

    )



    source_experiment = data["experiment"]



    source_service = data["source_service"]



    reused = await reuse_experiment(

        db=db_session,

        experiment_id=source_experiment.id,

        failure_overrides=[

            {

                "service_id": source_service.id,

                "failure_type": "timeout",

                "duration_seconds": 15,

                "parameters": {

                    "timeout_ms": 3000,

                },

            }

        ],

    )



    # Original failure was latency.

    # New configuration should contain

    # only the overridden timeout failure.



    assert len(reused.failures) == 1



    failure = reused.failures[0]



    assert (

        failure.service_id

        == source_service.id

    )



    assert failure.failure_type == "timeout"



    assert failure.duration_seconds == 15



    assert failure.parameters == {

        "timeout_ms": 3000

    }



    # Original remains unchanged.



    assert len(source_experiment.failures) == 1



    assert (

        source_experiment.failures[0].failure_type

        == "latency"

    )





# ============================================================

# REUSE EXPERIMENT - CUSTOM NAME AND DESCRIPTION

# ============================================================



@pytest.mark.asyncio

async def test_reuse_experiment_custom_name_description(

    db_session,

):



    data = await create_source_experiment(

        db_session

    )



    source_experiment = data["experiment"]



    reused = await reuse_experiment(

        db=db_session,

        experiment_id=source_experiment.id,

        new_name="Modified Experiment",

        new_description="Modified description",

    )



    assert reused.name == (

        "Modified Experiment"

    )



    assert reused.description == (

        "Modified description"

    )





# ============================================================

# REUSE EXPERIMENT - NOT FOUND

# ============================================================



@pytest.mark.asyncio

async def test_reuse_experiment_not_found(

    db_session,

):



    with pytest.raises(

        ValueError,

        match="Experiment not found",

    ):

        await reuse_experiment(

            db=db_session,

            experiment_id=uuid4(),

        )





# ============================================================

# GET EXPERIMENT CONFIGURATION

# ============================================================



@pytest.mark.asyncio

async def test_get_experiment_configuration(

    db_session,

):



    data = await create_source_experiment(

        db_session

    )



    source_experiment = data["experiment"]

    system = data["system"]



    configuration = (

        await get_experiment_configuration(

            db=db_session,

            experiment_id=source_experiment.id,

        )

    )



    # --------------------------------------------------------

    # EXPERIMENT

    # --------------------------------------------------------



    assert configuration.id == (

        source_experiment.id

    )



    assert configuration.name == (

        "Original Experiment"

    )



    # --------------------------------------------------------

    # SYSTEM

    # --------------------------------------------------------



    assert configuration.system is not None



    assert configuration.system.id == system.id



    # --------------------------------------------------------

    # SERVICES

    # --------------------------------------------------------



    assert len(

        configuration.system.services

    ) == 2



    # --------------------------------------------------------

    # DEPENDENCIES

    # --------------------------------------------------------



    total_dependencies = sum(

        len(service.outgoing_dependencies)

        for service in configuration.system.services

    )



    assert total_dependencies == 1



    # --------------------------------------------------------

    # WORKLOAD

    # --------------------------------------------------------



    assert configuration.workload is not None



    assert (

        configuration.workload.total_requests

        == 100

    )



    # --------------------------------------------------------

    # FAILURES

    # --------------------------------------------------------



    assert len(configuration.failures) == 1



    assert (

        configuration.failures[0].failure_type

        == "latency"

    )





# ============================================================

# GET EXPERIMENT CONFIGURATION - NOT FOUND

# ============================================================



@pytest.mark.asyncio

async def test_get_experiment_configuration_not_found(

    db_session,

):



    with pytest.raises(

        ValueError,

        match="Experiment not found",

    ):

        await get_experiment_configuration(

            db=db_session,

            experiment_id=uuid4(),

        )