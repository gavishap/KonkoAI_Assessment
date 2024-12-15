"""Base repository interface."""

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from ..domain.models import Conversation, Message


class Repository(ABC):
    """Abstract base class for repositories."""

    @abstractmethod
    async def get_conversation(self, conversation_id: UUID) -> Optional[Conversation]:
        """Retrieve a conversation by ID."""
        pass

    @abstractmethod
    async def list_conversations(self, limit: int = 100, offset: int = 0) -> List[Conversation]:
        """List all conversations with pagination."""
        pass

    @abstractmethod
    async def create_conversation(self) -> Conversation:
        """Create a new conversation."""
        pass

    @abstractmethod
    async def add_message(self, message: Message) -> Message:
        """Add a message to a conversation."""
        pass

    @abstractmethod
    async def get_messages(
        self, conversation_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[Message]:
        """Get messages for a conversation with pagination."""
        pass 
