"""Rate limiter implementation using sliding window algorithm."""

import asyncio
import re
import time
from collections import deque
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Deque, List

from fastapi import HTTPException, Request
from structlog import get_logger

logger = get_logger()

@dataclass
class SlidingWindow:
    """Sliding window for rate limiting."""
    
    window_size: float  # Window size in seconds
    max_requests: int   # Maximum requests per window
    requests: Deque[float]  # Timestamps of requests
    lock: asyncio.Lock

    def __init__(self, window_size: float, max_requests: int):
        """Initialize sliding window."""
        self.window_size = window_size
        self.max_requests = max_requests
        self.requests = deque()
        self.lock = asyncio.Lock()

    async def _cleanup_old_requests(self, now: float) -> None:
        """Remove requests outside the current window."""
        while self.requests and now - self.requests[0] > self.window_size:
            self.requests.popleft()

    async def try_acquire(self) -> bool:
        """Try to acquire a slot in the window."""
        async with self.lock:
            now = time.time()
            await self._cleanup_old_requests(now)
            
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
                
            return False

class RateLimiter:
    """Rate limiter with endpoint-specific limits."""

    def __init__(self, rate_limit: int = 50, time_window: int = 60):
        """Initialize rate limiter with configurable parameters."""
        self.rate_limit = rate_limit
        self.time_window = time_window  # in seconds
        self.requests: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task = None
        logger.info(
            "rate_limiter_initialized",
            rate_limit=rate_limit,
            time_window=time_window
        )

    async def start(self):
        """Start the rate limiter cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop(self):
        """Stop the rate limiter cleanup task."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    async def _periodic_cleanup(self):
        """Periodically clean up old request timestamps."""
        while True:
            try:
                await asyncio.sleep(self.time_window)
                async with self._lock:
                    current_time = time.time()
                    cutoff_time = current_time - self.time_window
                    
                    for key in list(self.requests.keys()):
                        self.requests[key] = [
                            ts for ts in self.requests[key]
                            if ts > cutoff_time
                        ]
                        if not self.requests[key]:
                            del self.requests[key]
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("rate_limiter_cleanup_error", error=str(e))

    async def check_rate_limit(self, key: str) -> None:
        """Check if the request should be rate limited."""
        # Ensure cleanup task is running
        await self.start()
        
        current_time = time.time()
        
        async with self._lock:
            if key not in self.requests:
                self.requests[key] = []
                
            # Remove old timestamps
            cutoff_time = current_time - self.time_window
            self.requests[key] = [
                ts for ts in self.requests[key]
                if ts > cutoff_time
            ]
            
            # Check rate limit
            if len(self.requests[key]) >= self.rate_limit:
                logger.warning(
                    "rate_limit_exceeded",
                    key=key,
                    current_requests=len(self.requests[key]),
                    rate_limit=self.rate_limit
                )
                raise RateLimitExceeded(
                    f"Rate limit of {self.rate_limit} requests per {self.time_window} seconds exceeded"
                )
                
            # Add new timestamp
            self.requests[key].append(current_time)
            logger.debug(
                "request_tracked",
                key=key,
                current_requests=len(self.requests[key]),
                rate_limit=self.rate_limit
            )

    async def get_remaining_requests(self, key: str) -> int:
        """Get remaining requests for the key."""
        # Ensure cleanup task is running
        await self.start()
        
        current_time = time.time()
        
        async with self._lock:
            if key not in self.requests:
                return self.rate_limit
                
            # Remove old timestamps
            cutoff_time = current_time - self.time_window
            self.requests[key] = [
                ts for ts in self.requests[key]
                if ts > cutoff_time
            ]
            
            return max(0, self.rate_limit - len(self.requests[key]))

    def __del__(self):
        """Cleanup when the rate limiter is destroyed."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()

class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""
    pass

async def rate_limit_middleware(
    request: Request,
    rate_limiter: Optional[RateLimiter] = None
) -> None:
    """Rate limiting middleware."""
    if rate_limiter is None:
        return

    client_ip = request.client.host if request.client else "unknown"
    path = request.url.path
    key = f"{client_ip}:{path}"

    await rate_limiter.check_rate_limit(key)
