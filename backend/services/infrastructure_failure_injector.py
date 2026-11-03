"""ResilienceLab infrastructure failure injectors.

Public function signatures are kept compatible with the existing callers.
Stress processes write their container-namespace PID to unique PID files.
"""

import asyncio
import ipaddress
import shlex
import uuid
from contextlib import asynccontextmanager

import docker


@asynccontextmanager
async def _container_context(container_name: str):
    client = docker.from_env()
    try:
        container = await asyncio.to_thread(client.containers.get, container_name)
        container.reload()
        if container.status != "running":
            raise RuntimeError(
                f"Container '{container_name}' must be running; "
                f"current status is '{container.status}'."
            )
        yield client, container
    finally:
        await asyncio.to_thread(client.close)


async def _run_checked(container, command: str, operation: str) -> str:
    result = await asyncio.to_thread(
        container.exec_run, ["sh", "-c", command], stdout=True, stderr=True
    )
    output = result.output or b""
    if isinstance(output, bytes):
        output = output.decode("utf-8", errors="replace")
    if result.exit_code != 0:
        raise RuntimeError(
            f"{operation} failed in '{container.name}' "
            f"(exit {result.exit_code}): {str(output).strip()}"
        )
    return str(output).strip()


def _positive_int(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return value


async def _start_detached_process(container, command: str, pid_file: str) -> int:
    info = await asyncio.to_thread(
        container.client.api.exec_create, container.id, ["sh", "-c", command]
    )
    await asyncio.to_thread(
        container.client.api.exec_start, info["Id"], detach=True
    )

    pid_file_q = shlex.quote(pid_file)
    for _ in range(50):
        try:
            output = await _run_checked(
                container,
                f"test -s {pid_file_q} && cat {pid_file_q}",
                "Waiting for stress process startup",
            )
            pid_text = output.strip()
            if pid_text.isdigit() and int(pid_text) > 1:
                await _run_checked(
                    container, f"kill -0 {int(pid_text)}",
                    "Verifying stress process startup",
                )
                return int(pid_text)
        except RuntimeError:
            pass
        await asyncio.sleep(0.1)

    raise RuntimeError(f"Stress process did not start; PID file: {pid_file}")


async def _stop_pidfile_process(container, pid_file: str) -> None:
    command = f"""
        set -eu
        pid_file={shlex.quote(pid_file)}
        if [ ! -s "$pid_file" ]; then rm -f "$pid_file"; exit 0; fi
        pid="$(cat "$pid_file")"
        case "$pid" in ''|*[!0-9]*)
            echo "Invalid PID in $pid_file" >&2; rm -f "$pid_file"; exit 1 ;;
        esac
        if [ "$pid" -le 1 ]; then
            echo "Refusing unsafe PID: $pid" >&2; rm -f "$pid_file"; exit 1
        fi
        kill -TERM "$pid" 2>/dev/null || true
        count=0
        while [ "$count" -lt 20 ]; do
            state="$(ps -o stat= -p "$pid" 2>/dev/null | tr -d ' ' || true)"
            case "$state" in ''|Z*) break ;; esac
            sleep 0.1
            count=$((count + 1))
        done
        state="$(ps -o stat= -p "$pid" 2>/dev/null | tr -d ' ' || true)"
        case "$state" in
            ''|Z*) ;;
            *)
                kill -KILL "$pid" 2>/dev/null || true
                sleep 0.1
                state="$(ps -o stat= -p "$pid" 2>/dev/null | tr -d ' ' || true)"
                case "$state" in ''|Z*) ;;
                    *) echo "PID $pid remains after SIGKILL" >&2; exit 1 ;;
                esac
                ;;
        esac
        rm -f "$pid_file"
    """
    await _run_checked(container, command, "Stress process cleanup")


async def _assert_default_root_qdisc(container) -> None:
    output = await _run_checked(
        container, "tc qdisc show dev eth0",
        "Checking existing traffic-control configuration",
    )
    roots = [line for line in output.splitlines() if " root " in f" {line} "]
    if roots and not all("noqueue" in line for line in roots):
        raise RuntimeError(
            "Refusing to replace an existing custom root qdisc on eth0: "
            + "; ".join(roots)
        )


async def _apply_qdisc(container, command: str) -> None:
    await _assert_default_root_qdisc(container)
    await _run_checked(container, command, "Applying network impairment")


async def _remove_root_qdisc(container) -> None:
    await _run_checked(
        container, "tc qdisc del dev eth0 root", "Removing network impairment"
    )


# CPU stress -----------------------------------------------------------------

async def inject_cpu_stress(
    container_name: str, duration_seconds: int, cpu_workers: int = 1
):
    duration_seconds = _positive_int(duration_seconds, "duration_seconds")
    cpu_workers = _positive_int(cpu_workers, "cpu_workers")

    async with _container_context(container_name) as (_, container):
        pid_files = []
        try:
            for _ in range(cpu_workers):
                pid_file = f"/tmp/resiliencelab_cpu_{uuid.uuid4().hex}.pid"
                pid_files.append(pid_file)
                command = (
                    f"printf '%s\\n' \"$$\" > {shlex.quote(pid_file)}; "
                    "while :; do :; done"
                )
                await _start_detached_process(container, command, pid_file)
            await asyncio.sleep(duration_seconds)
        finally:
            errors = []
            for pid_file in reversed(pid_files):
                try:
                    await _stop_pidfile_process(container, pid_file)
                except Exception as exc:
                    errors.append(str(exc))
            if errors:
                raise RuntimeError("CPU stress cleanup incomplete: " + " | ".join(errors))


# Memory stress --------------------------------------------------------------

async def inject_memory_stress(
    container_name: str, duration_seconds: int, memory_mb: int = 100
):
    duration_seconds = _positive_int(duration_seconds, "duration_seconds")
    memory_mb = _positive_int(memory_mb, "memory_mb")

    async with _container_context(container_name) as (_, container):
        pid_file = f"/tmp/resiliencelab_memory_{uuid.uuid4().hex}.pid"
        code = (
            "import os,time; "
            f"open({pid_file!r},'w').write(str(os.getpid())); "
            f"data=bytearray({memory_mb}*1024*1024); "
            f"time.sleep({duration_seconds + 60})"
        )
        command = f"python -c {shlex.quote(code)}"
        started = False
        try:
            await _start_detached_process(container, command, pid_file)
            started = True
            await asyncio.sleep(duration_seconds)
        finally:
            if started:
                await _stop_pidfile_process(container, pid_file)
            else:
                await _run_checked(
                    container, f"rm -f {shlex.quote(pid_file)}",
                    "Removing incomplete memory-stress PID file",
                )


# Network delay --------------------------------------------------------------

async def inject_network_delay(
    container_name: str, delay_ms: int, duration_seconds: int
):
    delay_ms = _positive_int(delay_ms, "delay_ms")
    duration_seconds = _positive_int(duration_seconds, "duration_seconds")
    async with _container_context(container_name) as (_, container):
        activated = False
        try:
            await _apply_qdisc(
                container,
                f"tc qdisc add dev eth0 root netem delay {delay_ms}ms",
            )
            activated = True
            await asyncio.sleep(duration_seconds)
        finally:
            if activated:
                await _remove_root_qdisc(container)


# Packet loss ----------------------------------------------------------------

async def inject_packet_loss(
    container_name: str, loss_percent: int, duration_seconds: int
):
    loss_percent = _positive_int(loss_percent, "loss_percent")
    duration_seconds = _positive_int(duration_seconds, "duration_seconds")
    if loss_percent > 100:
        raise ValueError("loss_percent must be between 1 and 100.")

    async with _container_context(container_name) as (_, container):
        activated = False
        try:
            await _apply_qdisc(
                container,
                f"tc qdisc add dev eth0 root netem loss {loss_percent}%",
            )
            activated = True
            await asyncio.sleep(duration_seconds)
        finally:
            if activated:
                await _remove_root_qdisc(container)


# Bandwidth limit ------------------------------------------------------------

async def inject_bandwidth_limit(
    container_name: str, bandwidth_mbps: int, duration_seconds: int
):
    bandwidth_mbps = _positive_int(bandwidth_mbps, "bandwidth_mbps")
    duration_seconds = _positive_int(duration_seconds, "duration_seconds")

    async with _container_context(container_name) as (_, container):
        activated = False
        try:
            await _apply_qdisc(
                container,
                "tc qdisc add dev eth0 root tbf "
                f"rate {bandwidth_mbps}mbit burst 32kbit latency 400ms",
            )
            activated = True
            await asyncio.sleep(duration_seconds)
        finally:
            if activated:
                await _remove_root_qdisc(container)


# Network partition ----------------------------------------------------------

async def inject_network_partition(
    source_container_name: str, target_container_name: str, duration_seconds: int
):
    duration_seconds = _positive_int(duration_seconds, "duration_seconds")
    client = docker.from_env()
    source = None
    target_ip = None
    rule_added = False
    cleanup_error = None

    try:
        source = await asyncio.to_thread(
            client.containers.get, source_container_name
        )
        target = await asyncio.to_thread(
            client.containers.get, target_container_name
        )
        await asyncio.to_thread(source.reload)
        await asyncio.to_thread(target.reload)
        if source.status != "running" or target.status != "running":
            raise RuntimeError("Both network-partition containers must be running.")

        source_nets = source.attrs.get("NetworkSettings", {}).get("Networks", {})
        target_nets = target.attrs.get("NetworkSettings", {}).get("Networks", {})
        shared = sorted(set(source_nets) & set(target_nets))
        if not shared:
            raise ValueError(
                f"'{source_container_name}' and '{target_container_name}' "
                "do not share a Docker network."
            )

        network = shared[0]
        target_ip = target_nets[network].get("IPAddress")
        if not target_ip:
            raise RuntimeError(
                f"Could not determine target IP on Docker network '{network}'."
            )
        target_ip = str(ipaddress.ip_address(target_ip))

        await _run_checked(
            source,
            f"iptables -I OUTPUT 1 -d {shlex.quote(target_ip)} -j DROP",
            "Activating network partition",
        )
        rule_added = True
        await asyncio.sleep(duration_seconds)
    finally:
        if rule_added and source is not None and target_ip:
            try:
                await _run_checked(
                    source,
                    f"iptables -D OUTPUT -d {shlex.quote(target_ip)} -j DROP",
                    "Removing network partition",
                )
            except Exception as exc:
                cleanup_error = exc
        await asyncio.to_thread(client.close)

    if cleanup_error:
        raise RuntimeError(f"Network partition cleanup failed: {cleanup_error}") from cleanup_error


# Container crash ------------------------------------------------------------

async def inject_container_crash(container_name: str, duration_seconds: int):
    duration_seconds = _positive_int(duration_seconds, "duration_seconds")
    client = docker.from_env()
    container = None
    stopped_by_injector = False
    try:
        container = await asyncio.to_thread(client.containers.get, container_name)
        await asyncio.to_thread(container.reload)
        if container.status != "running":
            raise RuntimeError(
                f"Container '{container_name}' must be running before crash injection."
            )
        await asyncio.to_thread(container.stop)
        stopped_by_injector = True
        await asyncio.sleep(duration_seconds)
    finally:
        try:
            if stopped_by_injector and container is not None:
                await asyncio.to_thread(container.start)
        finally:
            await asyncio.to_thread(client.close)


# Disk stress ----------------------------------------------------------------

async def inject_disk_stress(
    container_name: str, size_mb: int, duration_seconds: int
):
    size_mb = _positive_int(size_mb, "size_mb")
    duration_seconds = _positive_int(duration_seconds, "duration_seconds")

    async with _container_context(container_name) as (_, container):
        file_path = f"/tmp/resiliencelab_disk_stress_{uuid.uuid4().hex}"
        quoted_path = shlex.quote(file_path)
        created = False
        try:
            await _run_checked(
                container,
                f"dd if=/dev/zero of={quoted_path} "
                f"bs=1M count={size_mb} conv=fsync",
                "Creating disk-stress file",
            )
            created = True
            await asyncio.sleep(duration_seconds)
        finally:
            if created:
                await _run_checked(
                    container, f"rm -f {quoted_path}", "Removing disk-stress file"
                )
