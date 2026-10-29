
import asyncio
import time
import httpx

TOTAL_REQUESTS = 1000
CONCURRENCY = 50
URL = "http://localhost:8001/"


async def main():
    semaphore = asyncio.Semaphore(CONCURRENCY)
    results = []
    errors = []

    async with httpx.AsyncClient(timeout=30) as client:

        async def send_request():
            async with semaphore:
                start = time.perf_counter()

                try:
                    response = await client.get(URL)
                    latency = (time.perf_counter() - start) * 1000

                    results.append({
                        "status": response.status_code,
                        "latency": latency,
                    })

                except Exception as exc:
                    errors.append(str(exc))

        start_time = time.perf_counter()

        await asyncio.gather(
            *(send_request() for _ in range(TOTAL_REQUESTS))
        )

        duration = time.perf_counter() - start_time

    successful = sum(
        1 for result in results
        if 200 <= result["status"] < 400
    )

    failed = TOTAL_REQUESTS - successful

    latencies = sorted(
        result["latency"] for result in results
    )

    print("\n===== LOAD TEST RESULTS =====")
    print(f"Total requests: {TOTAL_REQUESTS}")
    print(f"Successful requests: {successful}")
    print(f"Failed requests: {failed}")
    print(f"Exceptions: {len(errors)}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Requests per second: {TOTAL_REQUESTS / duration:.2f}")

    if latencies:
        print(f"Average latency: {sum(latencies) / len(latencies):.2f} ms")
        print(f"P95 latency: {latencies[int(len(latencies) * 0.95) - 1]:.2f} ms")
        print(f"P99 latency: {latencies[int(len(latencies) * 0.99) - 1]:.2f} ms")

    print("=============================")


if __name__ == "__main__":
    asyncio.run(main())
