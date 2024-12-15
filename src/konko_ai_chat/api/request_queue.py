"""Request queue handler for high load scenarios."""

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional, List
from uuid import UUID
import structlog
from weakref import WeakKeyDictionary
from collections import OrderedDict
import contextlib

logger = structlog.get_logger()


@dataclass
class QueuedRequest:
    """Represents a queued request with its context."""
    
    conversation_id: UUID
    task: Callable[..., Awaitable[Any]]
    args: tuple
    kwargs: dict
    future: asyncio.Future
    sequence_number: int  # Added to maintain order


class RequestQueue:
    """Handles request queuing and processing."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super(RequestQueue, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        max_concurrent: int = 10,
        queue_timeout: float = 30.0  # 30 seconds default timeout
    ) -> None:
        """Initialize request queue with configurable concurrency."""
        self.max_concurrent = max_concurrent
        self.queue_timeout = queue_timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_requests = 0
        self._lock = asyncio.Lock()
        self.queues: Dict[UUID, asyncio.Queue] = {}
        self._tasks = WeakKeyDictionary()  # Use weak references to avoid memory leaks
        self._sequence_counters: Dict[UUID, int] = {}  # Track sequence numbers per conversation
        self._pending_requests: Dict[UUID, OrderedDict[int, QueuedRequest]] = {}  # Track pending requests
        self._initialized = True
        logger.info("request_queue_initialized", max_concurrent=max_concurrent)

    @contextlib.asynccontextmanager
    async def acquire(self):
        """Acquire a slot in the request queue."""
        try:
            async with self._lock:
                self.active_requests += 1
                
            async with self.semaphore:
                yield
                
        finally:
            async with self._lock:
                self.active_requests -= 1

    async def get_queue_length(self) -> int:
        """Get current queue length."""
        async with self._lock:
            return self.active_requests

    async def is_full(self) -> bool:
        """Check if queue is at capacity."""
        async with self._lock:
            return self.active_requests >= self.max_concurrent

    async def _get_queue(self, conversation_id: UUID) -> asyncio.Queue:
        """Get or create queue for conversation."""
        async with self._lock:
            if conversation_id not in self.queues:
                self.queues[conversation_id] = asyncio.Queue()
                self._sequence_counters[conversation_id] = 0
                self._pending_requests[conversation_id] = OrderedDict()
                # Start queue processor task
                task = asyncio.create_task(self._process_queue(conversation_id))
                self._tasks[task] = None  # Store task with weak reference
            return self.queues[conversation_id]

    async def _process_queue(self, conversation_id: UUID) -> None:
        """Process requests in the queue for a conversation."""
        queue = self.queues[conversation_id]
        pending = self._pending_requests[conversation_id]
        next_sequence = 0  # Track the next sequence number to process
        
        try:
            while True:
                request = await queue.get()
                try:
                    # Add request to pending
                    pending[request.sequence_number] = request
                    
                    # Process requests in strict sequence order
                    while next_sequence in pending:
                        next_request = pending.pop(next_sequence)
                        
                        async with self.semaphore:
                            try:
                                result = await asyncio.wait_for(
                                    next_request.task(*next_request.args, **next_request.kwargs),
                                    timeout=self.queue_timeout
                                )
                                if not next_request.future.done():
                                    next_request.future.set_result(result)
                            except asyncio.TimeoutError:
                                if not next_request.future.done():
                                    next_request.future.set_exception(
                                        TimeoutError("Request processing timed out")
                                    )
                            except Exception as e:
                                if not next_request.future.done():
                                    next_request.future.set_exception(e)
                                logger.error(
                                    "request_processing_error",
                                    conversation_id=str(conversation_id),
                                    sequence=next_sequence,
                                    error=str(e)
                                )
                        
                        queue.task_done()
                        next_sequence += 1  # Move to next sequence number
                        
                except Exception as e:
                    logger.error(
                        "queue_processing_error",
                        conversation_id=str(conversation_id),
                        error=str(e)
                    )
                    
        except asyncio.CancelledError:
            logger.info("queue_processor_cancelled", conversation_id=str(conversation_id))
        finally:
            async with self._lock:
                if conversation_id in self.queues and self.queues[conversation_id].empty():
                    del self.queues[conversation_id]
                    del self._sequence_counters[conversation_id]
                    del self._pending_requests[conversation_id]

    async def enqueue_request(
        self,
        conversation_id: UUID,
        task: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """Enqueue a request and wait for its execution."""
        queue = await self._get_queue(conversation_id)
        
        async with self._lock:
            sequence_number = self._sequence_counters[conversation_id]
            self._sequence_counters[conversation_id] += 1
            
        future = asyncio.Future()
        request = QueuedRequest(
            conversation_id=conversation_id,
            task=task,
            args=args,
            kwargs=kwargs,
            future=future,
            sequence_number=sequence_number
        )
        
        try:
            # Store request in pending dict and queue
            self._pending_requests[conversation_id][sequence_number] = request
            await queue.put(request)
            
            # Wait for result with timeout
            return await asyncio.wait_for(future, timeout=self.queue_timeout)
            
        except asyncio.TimeoutError:
            logger.error(
                "request_timeout",
                conversation_id=str(conversation_id),
                sequence=sequence_number
            )
            raise TimeoutError("Request processing timed out")
        except Exception as e:
            logger.error(
                "request_enqueue_error",
                conversation_id=str(conversation_id),
                sequence=sequence_number,
                error=str(e)
            )
            raise

    async def cleanup(self) -> None:
        """Clean up resources."""
        async with self._lock:
            # Cancel all queue processor tasks
            tasks = list(self._tasks.keys())
            for task in tasks:
                if not task.done():
                    task.cancel()
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # Clear all queues and tracking structures
            self.queues.clear()
            self._tasks.clear()
            self._sequence_counters.clear()
            self._pending_requests.clear()
            logger.info("request_queue_cleaned_up")


_request_queue: Optional[RequestQueue] = None


def get_request_queue() -> RequestQueue:
    """Get the global request queue instance."""
    global _request_queue
    if _request_queue is None:
        _request_queue = RequestQueue()
    return _request_queue


async def process_queued_request(
    conversation_id: UUID,
    task: Callable[..., Awaitable[Any]],
    *args: Any,
    **kwargs: Any
) -> Any:
    """Process a request through the queue."""
    queue = get_request_queue()
    return await queue.enqueue_request(conversation_id, task, *args, **kwargs)
