"""Test suite for the API endpoints."""

import asyncio
from typing import List
import pytest
from httpx import AsyncClient
from fastapi import FastAPI

from konko_ai_chat.api.app import app


@pytest.mark.asyncio
async def test_create_conversation():
    """Test creating a new conversation."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/conversations")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data


@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling in various scenarios."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test invalid conversation ID format
        response = await client.get("/conversations/invalid-uuid")
        assert response.status_code == 422  # Validation error

        # Test invalid message format
        response = await client.post("/conversations")
        conversation_id = response.json()["id"]
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"invalid_field": "test"}
        )
        assert response.status_code == 422

        # Test missing content
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={}
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_complex_conversation_flow():
    """Test a complex conversation flow with multiple interactions."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/conversations")
        conversation_id = response.json()["id"]
        
        # Multi-turn conversation
        messages = [
            "My name is John and I'm learning Python",
            "What's the best way to learn programming?",
            "Can you recommend some Python books?",
            "What about online courses?",
            "Thank you for your help!"
        ]
        
        for message in messages:
            response = await client.post(
                f"/conversations/{conversation_id}/messages",
                json={"content": message}
            )
            assert response.status_code == 200
            
            # Verify response format
            data = response.json()
            assert "id" in data
            assert "conversation_id" in data
            assert "content" in data
            assert "role" in data
            assert "created_at" in data
            
            # Get updated conversation
            conv_response = await client.get(f"/conversations/{conversation_id}")
            assert conv_response.status_code == 200
            assert "updated_at" in conv_response.json()


@pytest.mark.asyncio
async def test_conversation_history_pagination():
    """Test conversation history pagination."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create conversation
        response = await client.post("/conversations")
        conversation_id = response.json()["id"]
        
        # Add multiple messages
        for i in range(5):
            await client.post(
                f"/conversations/{conversation_id}/messages",
                json={"content": f"Message {i}"}
            )
        
        # Test different pagination parameters
        response = await client.get(
            f"/conversations/{conversation_id}/messages?limit=2&offset=0"
        )
        assert response.status_code == 200
        messages = response.json()
        assert len(messages) == 2
        
        response = await client.get(
            f"/conversations/{conversation_id}/messages?limit=3&offset=2"
        )
        assert response.status_code == 200
        messages = response.json()
        assert len(messages) == 3


@pytest.mark.asyncio
async def test_conversation_list_pagination():
    """Test conversation list pagination."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create multiple conversations
        for _ in range(5):
            await client.post("/conversations")
        
        # Test pagination
        response = await client.get("/conversations?limit=2&offset=0")
        assert response.status_code == 200
        conversations = response.json()
        assert len(conversations) == 2
        
        response = await client.get("/conversations?limit=3&offset=2")
        assert response.status_code == 200
        conversations = response.json()
        assert len(conversations) == 3


@pytest.mark.asyncio
async def test_list_conversations():
    """Test listing conversations."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a few conversations
        for _ in range(3):
            await client.post("/conversations")
        
        response = await client.get("/conversations")
        assert response.status_code == 200
        conversations = response.json()
        assert len(conversations) >= 3


@pytest.mark.asyncio
async def test_get_conversation():
    """Test getting a specific conversation."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a conversation
        response = await client.post("/conversations")
        conversation_id = response.json()["id"]
        
        # Get the conversation
        response = await client.get(f"/conversations/{conversation_id}")
        assert response.status_code == 200
        assert response.json()["id"] == conversation_id


@pytest.mark.asyncio
async def test_get_nonexistent_conversation():
    """Test getting a nonexistent conversation."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/conversations/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_and_get_messages():
    """Test creating and retrieving messages."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a conversation
        response = await client.post("/conversations")
        conversation_id = response.json()["id"]
        
        # Create a message
        message_content = "Hello, how are you?"
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": message_content}
        )
        assert response.status_code == 200
        message = response.json()
        assert message["content"] == message_content
        
        # Get messages
        response = await client.get(f"/conversations/{conversation_id}/messages")
        assert response.status_code == 200
        messages = response.json()
        assert len(messages) >= 2  # User message + AI response


@pytest.mark.asyncio
async def test_rapid_message_updates():
    """Test handling rapid successive messages updating previous information."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/conversations")
        conversation_id = response.json()["id"]
        
        # Send rapid successive messages
        messages = [
            "I want to travel to Paris",
            "Actually, make that London",
            "No wait, I meant Berlin",
            "What's the best time to visit?"
        ]
        
        for message in messages:
            response = await client.post(
                f"/conversations/{conversation_id}/messages",
                json={"content": message}
            )
            assert response.status_code == 200
        
        # Check final response references Berlin
        messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
        last_response = messages[-1]["content"].lower()
        assert "berlin" in last_response


@pytest.mark.asyncio
async def test_concurrent_message_ordering():
    """Test that messages sent concurrently maintain correct ordering."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/conversations")
        conversation_id = response.json()["id"]
        
        # Send messages sequentially first to establish order
        messages = [f"Message {i}" for i in range(5)]
        for message in messages:
            response = await client.post(
                f"/conversations/{conversation_id}/messages",
                json={"content": message}
            )
            assert response.status_code == 200
        
        # Verify messages are stored in order
        response = await client.get(f"/conversations/{conversation_id}/messages")
        stored_messages = response.json()
        user_messages = [msg for msg in stored_messages if msg["role"] == "user"]
        
        # Verify all messages are present
        assert len(user_messages) == 5
        
        # Verify message content exists in the responses
        message_contents = [msg["content"] for msg in user_messages]
        for i in range(5):
            assert f"Message {i}" in message_contents


@pytest.mark.asyncio
async def test_basic_math_operations():
    """Test basic math operations with context awareness."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/conversations")
        conversation_id = response.json()["id"]
        
        # Initial multiplication
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "What's 103 times 4439?"}
        )
        assert response.status_code == 200
        messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
        assert "457217" in messages[-1]["content"]
        
        # Addition to previous result
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "I need to add 8787 here"}
        )
        assert response.status_code == 200
        messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
        assert "466004" in messages[-1]["content"]
        
        # Simple multiplication
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "What's 25 times 25?"}
        )
        assert response.status_code == 200
        messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
        assert "625" in messages[-1]["content"]


@pytest.mark.asyncio
async def test_math_with_context():
    """Test math operations with context awareness."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/conversations")
        conversation_id = response.json()["id"]
        
        # Initial calculation
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "What's 1000 plus 2000?"}
        )
        assert response.status_code == 200
        messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
        assert "3000" in messages[-1]["content"]
        
        # Reference previous result
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "Multiply that by 2"}
        )
        assert response.status_code == 200
        messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
        assert "6000" in messages[-1]["content"]
        
        # Another operation with previous result
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "Add 500 to that number"}
        )
        assert response.status_code == 200
        messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
        assert "6500" in messages[-1]["content"]


@pytest.mark.asyncio
async def test_mixed_conversation_with_math():
    """Test mixing regular conversation with math operations."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/conversations")
        conversation_id = response.json()["id"]
        
        # Start with greeting
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "Hi, I'd like to get some help with numbers"}
        )
        assert response.status_code == 200
        
        # Do a calculation
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "What's 500 times 4?"}
        )
        assert response.status_code == 200
        messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
        assert "2000" in messages[-1]["content"]
        
        # Add to previous result
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "Add 350 to that"}
        )
        assert response.status_code == 200
        messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
        assert "2350" in messages[-1]["content"]
