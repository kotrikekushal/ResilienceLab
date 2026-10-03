import asyncio

import docker
import pytest

from backend.services.infrastructure_failure_injector import (
    inject_cpu_stress,
    inject_memory_stress,
    inject_network_delay,
    inject_packet_loss,
    inject_bandwidth_limit,
    inject_network_partition,
    inject_container_crash,
    inject_disk_stress,
)


TARGET_CONTAINER = "target-service"
DEPENDENCY_CONTAINER = "dependency-service"


# ============================================================
# DOCKER FIXTURE
# ============================================================

@pytest.fixture
def docker_client():
    client = docker.from_env()

    try:
        client.ping()
    except Exception:
        client.close()
        pytest.fail(
            "Docker daemon is not available."
        )

    yield client

    client.close()


# ============================================================
# TARGET SERVICE FIXTURE
# ============================================================

@pytest.fixture
def target_container(docker_client):
    try:
        container = docker_client.containers.get(
            TARGET_CONTAINER
        )
    except docker.errors.NotFound:
        pytest.fail(
            f"Docker container '{TARGET_CONTAINER}' "
            "was not found."
        )

    if container.status != "running":
        pytest.fail(
            f"Docker container '{TARGET_CONTAINER}' "
            f"is not running. Current status: "
            f"{container.status}"
        )

    return container


# ============================================================
# DEPENDENCY SERVICE FIXTURE
# ============================================================

@pytest.fixture
def dependency_container(docker_client):
    try:
        container = docker_client.containers.get(
            DEPENDENCY_CONTAINER
        )
    except docker.errors.NotFound:
        pytest.fail(
            f"Docker container '{DEPENDENCY_CONTAINER}' "
            "was not found."
        )

    if container.status != "running":
        pytest.fail(
            f"Docker container '{DEPENDENCY_CONTAINER}' "
            f"is not running. Current status: "
            f"{container.status}"
        )

    return container


# ============================================================
# CPU STRESS
# ============================================================

@pytest.mark.asyncio
async def test_inject_cpu_stress(
    docker_client,
    target_container,
):

    await inject_cpu_stress(
        container_name=TARGET_CONTAINER,
        duration_seconds=1,
        cpu_workers=1,
    )

    # The injector must clean up its CPU stress
    # after the duration finishes.

    target_container.reload()

    assert target_container.status == "running"


# ============================================================
# CPU STRESS - MULTIPLE WORKERS
# ============================================================

@pytest.mark.asyncio
async def test_inject_cpu_stress_multiple_workers(
    docker_client,
    target_container,
):

    await inject_cpu_stress(
        container_name=TARGET_CONTAINER,
        duration_seconds=1,
        cpu_workers=2,
    )

    target_container.reload()

    assert target_container.status == "running"


# ============================================================
# MEMORY STRESS
# ============================================================

@pytest.mark.asyncio
async def test_inject_memory_stress(
    docker_client,
    target_container,
):

    await inject_memory_stress(
        container_name=TARGET_CONTAINER,
        duration_seconds=1,
        memory_mb=10,
    )

    target_container.reload()

    assert target_container.status == "running"


# ============================================================
# NETWORK DELAY
# ============================================================

@pytest.mark.asyncio
async def test_inject_network_delay(
    docker_client,
    target_container,
):

    await inject_network_delay(
        container_name=TARGET_CONTAINER,
        delay_ms=10,
        duration_seconds=1,
    )

    target_container.reload()

    assert target_container.status == "running"

    # Verify the network qdisc was removed
    # by the injector's finally block.

    result = target_container.exec_run(
        [
            "sh",
            "-c",
            "tc qdisc show dev eth0",
        ]
    )

    output = result.output.decode(
        "utf-8",
        errors="ignore",
    )

    assert "netem" not in output


# ============================================================
# PACKET LOSS
# ============================================================

@pytest.mark.asyncio
async def test_inject_packet_loss(
    docker_client,
    target_container,
):

    await inject_packet_loss(
        container_name=TARGET_CONTAINER,
        loss_percent=10,
        duration_seconds=1,
    )

    target_container.reload()

    assert target_container.status == "running"

    # Verify packet-loss qdisc was removed.

    result = target_container.exec_run(
        [
            "sh",
            "-c",
            "tc qdisc show dev eth0",
        ]
    )

    output = result.output.decode(
        "utf-8",
        errors="ignore",
    )

    assert "netem" not in output


# ============================================================
# BANDWIDTH LIMIT
# ============================================================

@pytest.mark.asyncio
async def test_inject_bandwidth_limit(
    docker_client,
    target_container,
):

    await inject_bandwidth_limit(
        container_name=TARGET_CONTAINER,
        bandwidth_mbps=10,
        duration_seconds=1,
    )

    target_container.reload()

    assert target_container.status == "running"

    # Verify TBF qdisc was removed.

    result = target_container.exec_run(
        [
            "sh",
            "-c",
            "tc qdisc show dev eth0",
        ]
    )

    output = result.output.decode(
        "utf-8",
        errors="ignore",
    )

    assert "tbf" not in output


# ============================================================
# NETWORK PARTITION
# ============================================================

@pytest.mark.asyncio
async def test_inject_network_partition(
    docker_client,
    target_container,
    dependency_container,
):

    await inject_network_partition(
        source_container_name=TARGET_CONTAINER,
        target_container_name=DEPENDENCY_CONTAINER,
        duration_seconds=1,
    )

    target_container.reload()
    dependency_container.reload()

    assert target_container.status == "running"
    assert dependency_container.status == "running"

    # Find the dependency container IP on the
    # shared network.

    target_networks = (
        dependency_container.attrs
        .get("NetworkSettings", {})
        .get("Networks", {})
    )

    source_networks = (
        target_container.attrs
        .get("NetworkSettings", {})
        .get("Networks", {})
    )

    shared_networks = (
        set(source_networks.keys())
        & set(target_networks.keys())
    )

    assert shared_networks

    shared_network = next(
        iter(shared_networks)
    )

    dependency_ip = target_networks[
        shared_network
    ].get("IPAddress")

    assert dependency_ip

    # Verify the partition rule was removed.

    result = target_container.exec_run(
        [
            "sh",
            "-c",
            (
                f"iptables -C OUTPUT "
                f"-d {dependency_ip} "
                f"-j DROP"
            ),
        ]
    )

    # iptables -C returns 0 when the rule exists.
    # After cleanup the rule should NOT exist.

    assert result.exit_code != 0


# ============================================================
# CONTAINER CRASH
# ============================================================

@pytest.mark.asyncio
async def test_inject_container_crash(
    docker_client,
    target_container,
):

    original_container_id = target_container.id

    await inject_container_crash(
        container_name=TARGET_CONTAINER,
        duration_seconds=1,
    )

    target_container.reload()

    # The injector must restart the container
    # in its finally block.

    assert target_container.status == "running"

    assert target_container.id == (
        original_container_id
    )


# ============================================================
# DISK STRESS
# ============================================================

@pytest.mark.asyncio
async def test_inject_disk_stress(
    docker_client,
    target_container,
):

    file_path = (
        "/tmp/resiliencelab_disk_stress"
    )

    await inject_disk_stress(
        container_name=TARGET_CONTAINER,
        size_mb=1,
        duration_seconds=1,
    )

    target_container.reload()

    assert target_container.status == "running"

    # Verify the temporary stress file
    # was removed by the finally block.

    result = target_container.exec_run(
        [
            "sh",
            "-c",
            f"test ! -f {file_path}",
        ]
    )

    assert result.exit_code == 0