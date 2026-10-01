import asyncio

import docker


async def inject_cpu_stress(
    container_name: str,
    duration_seconds: int,
    cpu_workers: int = 1,
):
    client = docker.from_env()

    container = await asyncio.to_thread(
        client.containers.get,
        container_name,
    )

    exec_ids = []

    try:
        for _ in range(cpu_workers):

            exec_instance = await asyncio.to_thread(
                client.api.exec_create,
                container.id,
                [
                    "sh",
                    "-c",
                    "while true; do :; done",
                ],
            )

            exec_id = exec_instance["Id"]

            exec_ids.append(exec_id)

            await asyncio.to_thread(
                client.api.exec_start,
                exec_id,
                detach=True,
            )

        await asyncio.sleep(duration_seconds)

    finally:

        for exec_id in exec_ids:

            info = await asyncio.to_thread(
                client.api.exec_inspect,
                exec_id,
            )

            pid = info.get("Pid")

            if pid:

                kill_instance = await asyncio.to_thread(
                    client.api.exec_create,
                    container.id,
                    [
                        "kill",
                        "-TERM",
                        str(pid),
                    ],
                )

                await asyncio.to_thread(
                    client.api.exec_start,
                    kill_instance["Id"],
                    detach=True,
                )

        client.close()

async def inject_memory_stress(
    container_name: str,
    duration_seconds: int,
    memory_mb: int = 100,
):
    client = docker.from_env()

    container = await asyncio.to_thread(
        client.containers.get,
        container_name,
    )

    exec_instance = await asyncio.to_thread(
        client.api.exec_create,
        container.id,
        [
            "sh",
            "-c",
            f"""
            python -c "
import time
data = bytearray({memory_mb} * 1024 * 1024)
time.sleep({duration_seconds})
"
            """,
        ],
    )

    exec_id = exec_instance["Id"]

    try:
        await asyncio.to_thread(
            client.api.exec_start,
            exec_id,
            detach=True,
        )

        await asyncio.sleep(duration_seconds)

    finally:
        info = await asyncio.to_thread(
            client.api.exec_inspect,
            exec_id,
        )

        pid = info.get("Pid")

        if pid:
            kill_instance = await asyncio.to_thread(
                client.api.exec_create,
                container.id,
                [
                    "kill",
                    "-TERM",
                    str(pid),
                ],
            )

            await asyncio.to_thread(
                client.api.exec_start,
                kill_instance["Id"],
                detach=True,
            )

    client.close()

async def inject_network_delay(
    container_name: str,
    delay_ms: int,
    duration_seconds: int,
):
    client = docker.from_env()

    container = await asyncio.to_thread(
        client.containers.get,
        container_name,
    )

    try:
        # Add network delay to the container
        add_delay = await asyncio.to_thread(
            client.api.exec_create,
            container.id,
            [
                "sh",
                "-c",
                f"tc qdisc add dev eth0 root netem delay {delay_ms}ms",
            ],
        )

        await asyncio.to_thread(
            client.api.exec_start,
            add_delay["Id"],
        )

        # Keep the network delay active
        await asyncio.sleep(duration_seconds)

    finally:
        # Remove the network delay
        remove_delay = await asyncio.to_thread(
            client.api.exec_create,
            container.id,
            [
                "sh",
                "-c",
                "tc qdisc del dev eth0 root",
            ],
        )

        await asyncio.to_thread(
            client.api.exec_start,
            remove_delay["Id"],
        )

        client.close()

async def inject_packet_loss(
    container_name: str,
    loss_percent: int,
    duration_seconds: int,
):
    client = docker.from_env()

    container = await asyncio.to_thread(
        client.containers.get,
        container_name,
    )

    try:
        # Add packet loss to the container
        add_loss = await asyncio.to_thread(
            client.api.exec_create,
            container.id,
            [
                "sh",
                "-c",
                f"tc qdisc add dev eth0 root netem loss {loss_percent}%",
            ],
        )

        await asyncio.to_thread(
            client.api.exec_start,
            add_loss["Id"],
        )

        # Keep packet loss active
        await asyncio.sleep(duration_seconds)

    finally:
        # Remove packet loss
        remove_loss = await asyncio.to_thread(
            client.api.exec_create,
            container.id,
            [
                "sh",
                "-c",
                "tc qdisc del dev eth0 root",
            ],
        )

        await asyncio.to_thread(
            client.api.exec_start,
            remove_loss["Id"],
        )

        client.close()

async def inject_bandwidth_limit(
    container_name: str,
    bandwidth_mbps: int,
    duration_seconds: int,
):
    client = docker.from_env()

    container = await asyncio.to_thread(
        client.containers.get,
        container_name,
    )

    try:
        # Limit network bandwidth
        add_limit = await asyncio.to_thread(
            client.api.exec_create,
            container.id,
            [
                "sh",
                "-c",
                f"tc qdisc add dev eth0 root tbf rate "
                f"{bandwidth_mbps}mbit burst 32kbit latency 400ms",
            ],
        )

        await asyncio.to_thread(
            client.api.exec_start,
            add_limit["Id"],
        )

        # Keep the bandwidth limit active
        await asyncio.sleep(duration_seconds)

    finally:
        # Remove bandwidth limit
        remove_limit = await asyncio.to_thread(
            client.api.exec_create,
            container.id,
            [
                "sh",
                "-c",
                "tc qdisc del dev eth0 root",
            ],
        )

        await asyncio.to_thread(
            client.api.exec_start,
            remove_limit["Id"],
        )

        client.close()

async def inject_network_partition(
    source_container_name: str,
    target_container_name: str,
    duration_seconds: int,
):
    client = docker.from_env()

    source_container = await asyncio.to_thread(
        client.containers.get,
        source_container_name,
    )

    target_container = await asyncio.to_thread(
        client.containers.get,
        target_container_name,
    )

    # ------------------------------------------------------------
    # FIND A NETWORK SHARED BY SOURCE AND TARGET
    # ------------------------------------------------------------

    source_networks = (
        source_container.attrs
        .get("NetworkSettings", {})
        .get("Networks", {})
    )

    target_networks = (
        target_container.attrs
        .get("NetworkSettings", {})
        .get("Networks", {})
    )

    shared_networks = set(source_networks.keys()) & set(
        target_networks.keys()
    )

    if not shared_networks:
        client.close()
        raise ValueError(
            f"Containers '{source_container_name}' and "
            f"'{target_container_name}' do not share a Docker network"
        )

    # Use the first shared network.
    shared_network = next(iter(shared_networks))

    target_container_ip = target_networks[shared_network].get(
        "IPAddress"
    )

    if not target_container_ip:
        client.close()
        raise ValueError(
            f"Could not determine IP address of "
            f"'{target_container_name}' on network "
            f"'{shared_network}'"
        )

    try:
        # --------------------------------------------------------
        # BLOCK TRAFFIC FROM SOURCE → TARGET
        # --------------------------------------------------------

        add_partition = await asyncio.to_thread(
            client.api.exec_create,
            source_container.id,
            [
                "sh",
                "-c",
                f"iptables -A OUTPUT -d {target_container_ip} -j DROP",
            ],
        )

        await asyncio.to_thread(
            client.api.exec_start,
            add_partition["Id"],
        )

        # Keep partition active
        await asyncio.sleep(duration_seconds)

    finally:
        # --------------------------------------------------------
        # REMOVE PARTITION
        # --------------------------------------------------------

        remove_partition = await asyncio.to_thread(
            client.api.exec_create,
            source_container.id,
            [
                "sh",
                "-c",
                f"iptables -D OUTPUT -d {target_container_ip} -j DROP",
            ],
        )

        await asyncio.to_thread(
            client.api.exec_start,
            remove_partition["Id"],
        )

        client.close()
        
async def inject_container_crash(
    container_name: str,
    duration_seconds: int,
):
    client = docker.from_env()

    container = await asyncio.to_thread(
        client.containers.get,
        container_name,
    )

    try:
        # Stop the target container
        await asyncio.to_thread(
            container.stop,
        )

        # Keep the container stopped
        await asyncio.sleep(duration_seconds)

    finally:
        # Start the container again
        await asyncio.to_thread(
            container.start,
        )

        client.close()

async def inject_disk_stress(
    container_name: str,
    size_mb: int,
    duration_seconds: int,
):
    client = docker.from_env()

    container = await asyncio.to_thread(
        client.containers.get,
        container_name,
    )

    file_path = "/tmp/resiliencelab_disk_stress"

    try:
        # Create a temporary file that consumes disk space
        create_file = await asyncio.to_thread(
            client.api.exec_create,
            container.id,
            [
                "sh",
                "-c",
                f"dd if=/dev/zero of={file_path} "
                f"bs=1M count={size_mb}",
            ],
        )

        await asyncio.to_thread(
            client.api.exec_start,
            create_file["Id"],
        )

        # Keep the disk pressure for the configured duration
        await asyncio.sleep(duration_seconds)

    finally:
        # Remove the temporary file
        remove_file = await asyncio.to_thread(
            client.api.exec_create,
            container.id,
            [
                "sh",
                "-c",
                f"rm -f {file_path}",
            ],
        )

        await asyncio.to_thread(
            client.api.exec_start,
            remove_file["Id"],
        )

        client.close()