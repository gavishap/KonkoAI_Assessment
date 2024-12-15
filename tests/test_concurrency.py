"""Test suite for concurrent operations."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from konko_ai_chat.api.app import app


@pytest.mark.asyncio
async def test_concurrent_conversations():
    """Test handling multiple concurrent conversations."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create multiple conversations concurrently
        responses = await asyncio.gather(
            *[client.post("/conversations") for _ in range(10)]
        )
        
        # Verify all conversations were created successfully
        assert all(r.status_code == 200 for r in responses)
        conversation_ids = [r.json()["id"] for r in responses]
        assert len(set(conversation_ids)) == 10  # All IDs should be unique


@pytest.mark.asyncio
async def test_concurrent_messages():
    """Test sending messages concurrently to the same conversation."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a conversation
        response = await client.post("/conversations")
        conversation_id = response.json()["id"]

        # Send multiple messages concurrently
        messages = [
            {"content": f"What's {i} times {i+1}?"} for i in range(1, 6)
        ]
        responses = await asyncio.gather(
            *[
                client.post(f"/conversations/{conversation_id}/messages", json=msg)
                for msg in messages
            ]
        )

        # Verify all messages were processed
        assert all(r.status_code == 200 for r in responses)
        
        # Get all messages and verify order
        response = await client.get(f"/conversations/{conversation_id}/messages")
        all_messages = response.json()
        assert len(all_messages) == 10  # 5 user messages + 5 AI responses


@pytest.mark.asyncio
async def test_parallel_math_operations():
    """Test performing multiple math operations in parallel."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create conversations for parallel operations
        conv_responses = await asyncio.gather(
            *[client.post("/conversations") for _ in range(5)]
        )
        conversation_ids = [r.json()["id"] for r in conv_responses]

        # Test cases for math operations
        operations = [
            ("What's 103 times 4439?", "457217"),
            ("What's 200 times 300?", "60000"),
            ("What's 1234 plus 5678?", "6912"),
            ("What's 9999 minus 8888?", "1111"),
            ("What's 1000000 divided by 1000?", "1000")
        ]

        # Send operations to different conversations in parallel
        async def process_operation(conv_id: UUID, operation: tuple):
            response = await client.post(
                f"/conversations/{conv_id}/messages",
                json={"content": operation[0]}
            )
            assert response.status_code == 200
            messages = (await client.get(f"/conversations/{conv_id}/messages")).json()
            assert operation[1] in messages[1]["content"]

        await asyncio.gather(
            *[
                process_operation(conv_id, op)
                for conv_id, op in zip(conversation_ids, operations)
            ]
        )


@pytest.mark.asyncio
async def test_concurrent_error_handling():
    """Test error handling under concurrent load."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Try to access multiple non-existent conversations concurrently
        bad_ids = [f"00000000-0000-0000-0000-{i:012d}" for i in range(5)]
        responses = await asyncio.gather(
            *[
                client.get(f"/conversations/{conv_id}")
                for conv_id in bad_ids
            ],
            return_exceptions=True
        )
        assert all(r.status_code == 404 for r in responses)


@pytest.mark.asyncio
async def test_high_concurrency_load():
    """Test system under high concurrent load."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a single conversation for high load
        response = await client.post("/conversations")
        conversation_id = response.json()["id"]

        # Generate many concurrent requests
        num_requests = 50
        messages = [
            {"content": f"What's {i} plus {i}?"} for i in range(num_requests)
        ]
        
        # Send requests in batches to avoid overwhelming the system
        batch_size = 10
        for i in range(0, num_requests, batch_size):
            batch = messages[i:i + batch_size]
            responses = await asyncio.gather(
                *[
                    client.post(f"/conversations/{conversation_id}/messages", json=msg)
                    for msg in batch
                ]
            )
            assert all(r.status_code == 200 for r in responses)

        # Verify all messages were processed
        response = await client.get(f"/conversations/{conversation_id}/messages")
        all_messages = response.json()
        assert len(all_messages) == num_requests * 2  # User messages + AI responses
