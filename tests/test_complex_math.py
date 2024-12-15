"""Test complex math operations with context awareness."""

import pytest
from httpx import AsyncClient
from konko_ai_chat.api.app import app

@pytest.mark.asyncio
async def test_complex_math_operations():
    """Test complex math operations with various phrasings."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/conversations")
        conversation_id = response.json()["id"]

        # Initial calculation
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "What's 25 times 4?"}
        )
        assert response.status_code == 200
        messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
        assert "100" in messages[-1]["content"]

        # Reference previous result with "that"
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "multiply that by 5"}
        )
        assert response.status_code == 200
        messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
        assert "500" in messages[-1]["content"]

        # Use "this" instead of "that"
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "take this and add 50"}
        )
        assert response.status_code == 200
        messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
        assert "550" in messages[-1]["content"]

        # Mix operation words
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "times that by 2"}
        )
        assert response.status_code == 200
        messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
        assert "1100" in messages[-1]["content"]

@pytest.mark.asyncio
async def test_mixed_operations_with_context():
    """Test mixed operations using previous results."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/conversations")
        conversation_id = response.json()["id"]

        # Start with a simple calculation
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "Start with 1000"}
        )
        assert response.status_code == 200
        messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
        assert "1000" in messages[-1]["content"]

        # Subtract using "take away"
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "take away 200 from that"}
        )
        assert response.status_code == 200
        messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
        assert "800" in messages[-1]["content"]

        # Multiply using "times by"
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "times that by 3"}
        )
        assert response.status_code == 200
        messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
        assert "2400" in messages[-1]["content"]

        # Divide using informal language
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "now divide this by 8"}
        )
        assert response.status_code == 200
        messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
        assert "300" in messages[-1]["content"]

@pytest.mark.asyncio
async def test_complex_chained_operations():
    """Test complex chained operations with various phrasings."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/conversations")
        conversation_id = response.json()["id"]

        # Initial value
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "Let's start with 50"}
        )
        assert response.status_code == 200
        messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
        assert "50" in messages[-1]["content"]

        # Chain of operations with different phrasings
        operations = [
            ("multiply this by 4", "200"),
            ("add 150 to that", "350"),
            ("take that number and divide by 2", "175"),
            ("times it by 3", "525"),
            ("subtract 25 from this", "500"),
            ("double that", "1000"),
            ("take half of this", "500"),
            ("add 75 to it", "575"),
            ("times that by 2", "1150"),
            ("divide this by 5", "230")
        ]

        for operation, expected in operations:
            response = await client.post(
                f"/conversations/{conversation_id}/messages",
                json={"content": operation}
            )
            assert response.status_code == 200
            messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
            assert expected in messages[-1]["content"]

@pytest.mark.asyncio
async def test_informal_math_language():
    """Test informal mathematical language and expressions."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/conversations")
        conversation_id = response.json()["id"]

        # Start with a number
        response = await client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": "start with the number 100"}
        )
        assert response.status_code == 200
        messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
        assert "100" in messages[-1]["content"]

        # Test various informal expressions
        expressions = [
            ("double it", "200"),
            ("triple that", "600"),
            ("cut this in half", "300"),
            ("add another 50 to it", "350"),
            ("take away 30", "320"),
            ("multiply it by ten", "3200"),
            ("knock off 200", "3000"),
            ("add a hundred", "3100"),
            ("times by 2", "6200"),
            ("divide by 100", "62")
        ]

        for expr, expected in expressions:
            response = await client.post(
                f"/conversations/{conversation_id}/messages",
                json={"content": expr}
            )
            assert response.status_code == 200
            messages = (await client.get(f"/conversations/{conversation_id}/messages")).json()
            assert expected in messages[-1]["content"] 
