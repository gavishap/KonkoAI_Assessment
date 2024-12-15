"""Performance test suite."""

import asyncio
import time
from statistics import mean, median
from typing import List

import pytest
from httpx import AsyncClient

from konko_ai_chat.api.app import app


async def measure_response_time(client: AsyncClient, url: str, method: str = "GET", json: dict = None) -> float:
    """Measure response time for a request."""
    start_time = time.time()
    if method == "GET":
        await client.get(url)
    else:
        await client.post(url, json=json)
    return time.time() - start_time


@pytest.mark.asyncio
async def test_response_times():
    """Test response times under normal load."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a conversation
        response = await client.post("/conversations")
        conversation_id = response.json()["id"]

        # Measure response times for different operations
        times = {
            "create_conversation": [],
            "get_conversation": [],
            "list_conversations": [],
            "create_message": [],
            "get_messages": []
        }

        # Run each operation multiple times
        for _ in range(10):
            times["create_conversation"].append(
                await measure_response_time(client, "/conversations", method="POST")
            )
            times["get_conversation"].append(
                await measure_response_time(client, f"/conversations/{conversation_id}")
            )
            times["list_conversations"].append(
                await measure_response_time(client, "/conversations")
            )
            times["create_message"].append(
                await measure_response_time(
                    client,
                    f"/conversations/{conversation_id}/messages",
                    method="POST",
                    json={"content": "What's 2 plus 2?"}
                )
            )
            times["get_messages"].append(
                await measure_response_time(client, f"/conversations/{conversation_id}/messages")
            )

        # Assert reasonable response times
        for operation, measurements in times.items():
            avg_time = mean(measurements)
            med_time = median(measurements)
            print(f"{operation}: avg={avg_time:.3f}s, median={med_time:.3f}s")
            assert avg_time < 1.0, f"{operation} average time too high: {avg_time:.3f}s"


@pytest.mark.asyncio
async def test_concurrent_load_performance():
    """Test performance under concurrent load."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a conversation
        response = await client.post("/conversations")
        conversation_id = response.json()["id"]

        # Prepare concurrent requests
        num_requests = 50
        start_time = time.time()
        
        # Send concurrent requests
        responses = await asyncio.gather(
            *[
                client.post(
                    f"/conversations/{conversation_id}/messages",
                    json={"content": f"What's {i} plus {i}?"}
                )
                for i in range(num_requests)
            ]
        )
        
        total_time = time.time() - start_time
        requests_per_second = num_requests / total_time
        
        print(f"Processed {num_requests} requests in {total_time:.2f}s")
        print(f"Average throughput: {requests_per_second:.2f} requests/second")
        
        # Assert reasonable throughput
        assert requests_per_second > 5.0, f"Throughput too low: {requests_per_second:.2f} req/s"


@pytest.mark.asyncio
async def test_memory_usage():
    """Test memory usage under load."""
    try:
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Create multiple conversations and messages
            for _ in range(10):
                response = await client.post("/conversations")
                conversation_id = response.json()["id"]
                
                # Send multiple messages to each conversation
                for i in range(10):
                    await client.post(
                        f"/conversations/{conversation_id}/messages",
                        json={"content": f"What's {i} times {i}?"}
                    )
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        print(f"Memory usage increased by {memory_increase:.2f}MB")
        # Assert reasonable memory growth
        assert memory_increase < 100, f"Memory growth too high: {memory_increase:.2f}MB"
    except ImportError:
        pytest.skip("psutil not installed")
