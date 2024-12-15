"""Domain models for the chat application."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Message(BaseModel):
    """Message model."""

    id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID
    content: str
    role: str = "user"  # "user" or "assistant"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    context: Optional[str] = None


class Conversation(BaseModel):
    """Conversation model."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    messages: List[Message] = []
