"""In-memory repository implementation."""

import asyncio
from typing import Dict, List, Optional
from uuid import UUID
import structlog
from threading import Lock

from ..domain.models import Conversation, Message
from .base import Repository

logger = structlog.get_logger()

class InMemoryRepository(Repository):
    """Thread-safe in-memory repository implementation."""
    
    _instance = None
    _lock = Lock()
    _initialized = False
    
    def __new__(cls):
        """Ensure singleton pattern."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(InMemoryRepository, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        """Initialize the repository with thread-safe storage."""
        with self._lock:
            if self._initialized:
                return
                
            self._conversations: Dict[UUID, Conversation] = {}
            self._messages: Dict[UUID, List[Message]] = {}
            self._async_lock = asyncio.Lock()
            self._initialized = True
            logger.info("repository_initialized")

    async def get_conversation(self, conversation_id: UUID) -> Optional[Conversation]:
        """Retrieve a conversation by ID."""
        async with self._async_lock:
            conversation = self._conversations.get(conversation_id)
            if conversation is None:
                logger.warning("conversation_not_found", conversation_id=str(conversation_id))
            return conversation

    async def list_conversations(self, limit: int = 100, offset: int = 0) -> List[Conversation]:
        """List all conversations with pagination."""
        async with self._async_lock:
            conversations = sorted(
                self._conversations.values(),
                key=lambda c: c.updated_at,
                reverse=True
            )
            return conversations[offset : offset + limit]

    async def create_conversation(self) -> Conversation:
        """Create a new conversation."""
        conversation = Conversation()
        async with self._async_lock:
            self._conversations[conversation.id] = conversation
            self._messages[conversation.id] = []
            logger.info("conversation_created", conversation_id=str(conversation.id))
        return conversation

    async def add_message(self, message: Message) -> Message:
        """Add a message to a conversation."""
        async with self._async_lock:
            conversation = self._conversations.get(message.conversation_id)
            if not conversation:
                logger.error(
                    "conversation_not_found_for_message",
                    conversation_id=str(message.conversation_id)
                )
                raise ValueError(f"Conversation {message.conversation_id} not found")
            
            # Ensure message lists exist
            if message.conversation_id not in self._messages:
                self._messages[message.conversation_id] = []
            
            # Add message to both storage locations
            self._messages[message.conversation_id].append(message)
            conversation.messages = self._messages[message.conversation_id]
            conversation.updated_at = message.created_at
            
            logger.info(
                "message_added",
                conversation_id=str(message.conversation_id),
                message_role=message.role
            )
            return message

    async def get_messages(
        self, conversation_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[Message]:
        """Get messages for a conversation with pagination."""
        async with self._async_lock:
            if conversation_id not in self._conversations:
                logger.error(
                    "conversation_not_found_for_messages",
                    conversation_id=str(conversation_id)
                )
                raise ValueError(f"Conversation {conversation_id} not found")
                
            messages = self._messages.get(conversation_id, [])
            return sorted(
                messages[offset : offset + limit],
                key=lambda m: m.created_at
            )
