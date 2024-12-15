"""
FastAPI Application Module

A production-ready chat API enabling real-time AI conversations. Built with
reliability and scalability in mind through proven architectural patterns.

Key Features:
- Async request handling with FastAPI
- Rate limiting and request queuing
- Structured logging and metrics
- CORS and OpenTelemetry support

The app manages conversations and messages while ensuring stability under load
through careful resource management and error handling.
"""

from typing import List
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import Counter, generate_latest, CollectorRegistry
from pydantic import BaseModel
from structlog import get_logger
import asyncio
from contextlib import asynccontextmanager

from ..domain.models import Conversation, Message
from ..repositories.memory import InMemoryRepository
from ..services.llm import LLMService
from .rate_limiter import RateLimiter, rate_limit_middleware
from .request_queue import process_queued_request, get_request_queue, RequestQueue

# Registry for isolated metric collection
CUSTOM_REGISTRY = CollectorRegistry()

# Core operational metrics for monitoring
REQUESTS = Counter("requests_total", "Total requests by endpoint", registry=CUSTOM_REGISTRY)
ERRORS = Counter("errors_total", "Total errors by endpoint", registry=CUSTOM_REGISTRY)
PROCESSING_TIME = Counter("processing_time_seconds", "Total processing time by endpoint", registry=CUSTOM_REGISTRY)

logger = get_logger()

class MessageCreate(BaseModel):
    """Defines the structure for message creation requests"""
    content: str

# Core service instances
repository = InMemoryRepository()
llm_service = LLMService()

# Configure rate limits based on environment
is_test = __name__ == "konko_ai_chat.api.app"
rate_limiter = RateLimiter(
    rate_limit=100 if is_test else 50,
    time_window=30 if is_test else 60
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles app startup/shutdown and resource management"""
    queue = get_request_queue()
    await rate_limiter.start()
    logger.info("application_startup_complete")
    
    yield
    
    await queue.cleanup()
    await rate_limiter.stop()
    logger.info("application_shutdown_complete")

def get_repository() -> InMemoryRepository:
    """Returns the conversation storage instance"""
    return repository

def get_llm_service() -> LLMService:
    """Returns the language model service"""
    return llm_service

def get_rate_limiter() -> RateLimiter:
    """Returns the rate limiting service"""
    return rate_limiter

app = FastAPI(
    title="Konko AI Chat API",
    description="A production-grade async chat API with LLM integration",
    version="0.1.0",
    lifespan=lifespan
)

# Enable cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up request tracing
FastAPIInstrumentor.instrument_app(app)

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Tracks requests and enforces rate limits"""
    logger.info("request_started", path=request.url.path)
    try:
        await rate_limit_middleware(request, get_rate_limiter())
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error("request_failed", path=request.url.path, error=str(e))
        raise

@app.get("/conversations", response_model=List[Conversation])
async def list_conversations(
    limit: int = 100,
    offset: int = 0,
    repository: InMemoryRepository = Depends(get_repository)
) -> List[Conversation]:
    """Gets paginated conversation list with specified limit and offset"""
    try:
        return await repository.list_conversations(limit=limit, offset=offset)
    except Exception as e:
        logger.error("list_conversations_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list conversations")

@app.post("/conversations", response_model=Conversation)
async def create_conversation(
    repository: InMemoryRepository = Depends(get_repository)
) -> Conversation:
    """Starts a new conversation thread"""
    try:
        conversation = await repository.create_conversation()
        logger.info("conversation_created", conversation_id=str(conversation.id))
        return conversation
    except Exception as e:
        logger.error("create_conversation_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create conversation")

@app.get("/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(
    conversation_id: UUID,
    repository: InMemoryRepository = Depends(get_repository)
) -> Conversation:
    """Retrieves a specific conversation by its ID"""
    try:
        conversation = await repository.get_conversation(conversation_id)
        if not conversation:
            logger.warning("conversation_not_found", conversation_id=str(conversation_id))
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_conversation_error", conversation_id=str(conversation_id), error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get conversation")

@app.get("/conversations/{conversation_id}/messages", response_model=List[Message])
async def get_messages(
    conversation_id: UUID,
    limit: int = 100,
    offset: int = 0,
    repository: InMemoryRepository = Depends(get_repository)
) -> List[Message]:
    """Gets paginated message history for a conversation"""
    try:
        return await repository.get_messages(
            conversation_id, limit=limit, offset=offset
        )
    except ValueError:
        logger.warning("conversation_not_found_for_messages", conversation_id=str(conversation_id))
        raise HTTPException(status_code=404, detail="Conversation not found")
    except Exception as e:
        logger.error("get_messages_error", conversation_id=str(conversation_id), error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get messages")

@app.post("/conversations/{conversation_id}/messages", response_model=Message)
async def create_message(
    conversation_id: UUID,
    message: MessageCreate,
    repository: InMemoryRepository = Depends(get_repository),
    llm_service: LLMService = Depends(get_llm_service)
) -> Message:
    """
    Processes user message and generates AI response.
    Handles message queueing and conversation context.
    """
    async def process_message() -> Message:
        try:
            conversation = await repository.get_conversation(conversation_id)
            if not conversation:
                logger.warning("conversation_not_found_for_message", conversation_id=str(conversation_id))
                raise HTTPException(status_code=404, detail="Conversation not found")

            user_message = Message(conversation_id=conversation_id, content=message.content, role="user")
            await repository.add_message(user_message)

            messages = await repository.get_messages(conversation_id)

            ai_response = await llm_service.process_message(messages)
            ai_message = Message(
                conversation_id=conversation_id,
                content=ai_response,
                role="assistant"
            )
            await repository.add_message(ai_message)
            
            logger.info(
                "message_processed",
                conversation_id=str(conversation_id),
                user_message_length=len(message.content),
                ai_response_length=len(ai_response)
            )
            
            return user_message

        except HTTPException:
            raise
        except Exception as e:
            logger.error("create_message_error", conversation_id=str(conversation_id), error=str(e))
            raise HTTPException(status_code=500, detail="Failed to process message")

    try:
        return await process_queued_request(conversation_id, process_message)
    except TimeoutError:
        raise HTTPException(status_code=408, detail="Request timeout")
    except Exception as e:
        logger.error("queue_processing_error", conversation_id=str(conversation_id), error=str(e))
        raise HTTPException(status_code=500, detail="Failed to process message")

@app.get("/metrics")
async def metrics():
    """Provides Prometheus metrics for system monitoring"""
    return Response(generate_latest(CUSTOM_REGISTRY), media_type="text/plain")
