"""
Backpressure and rate limiting utilities for external service calls.

Provides circuit breaker pattern, request queuing, and rate limit handling
to ensure graceful degradation when external services are under load.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking requests (too many failures)
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = 5  # Failures before opening circuit
    success_threshold: int = 2  # Successes in half-open before closing
    timeout_seconds: float = 60.0  # Time to wait before trying half-open
    window_seconds: float = 60.0  # Sliding window for failure counting


class CircuitBreaker:  # pylint: disable=too-many-instance-attributes
    """
    Circuit breaker pattern implementation.

    Prevents cascading failures by stopping requests to a failing service
    after a threshold of failures, allowing time for recovery.
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize circuit breaker.

        Parameters
        ----------
        name : str
            Identifier for this circuit (e.g., "horreum-http")
        config : CircuitBreakerConfig, optional
            Configuration parameters, uses defaults if None
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.opened_at: Optional[float] = None
        self._lock = asyncio.Lock()

    async def call(self, func, *args, **kwargs):
        """
        Execute function through circuit breaker.

        Parameters
        ----------
        func : callable
            Async function to execute
        *args, **kwargs
            Arguments to pass to function

        Returns
        -------
        Any
            Result from function

        Raises
        ------
        RuntimeError
            If circuit is open (service unavailable)
        Exception
            Any exception raised by the function
        """
        async with self._lock:
            current_state = self.state

        if current_state == CircuitState.OPEN:
            # Check if timeout has passed
            if (
                self.opened_at
                and time.time() - self.opened_at >= self.config.timeout_seconds
            ):
                async with self._lock:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                logger.info(
                    f"circuit_breaker.{self.name}.half_open",
                    extra={"state_change": "open -> half_open"},
                )
            else:
                # Circuit still open, reject request
                logger.warning(
                    f"circuit_breaker.{self.name}.blocked",
                    extra={
                        "state": "open",
                        "opened_at": self.opened_at,
                        "timeout": self.config.timeout_seconds,
                    },
                )
                raise RuntimeError(
                    f"Circuit breaker '{self.name}' is OPEN - service unavailable. "
                    f"Try again in {self.config.timeout_seconds}s."
                )

        # Execute function
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as exc:
            await self._on_failure(exc)
            raise

    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.last_failure_time = None
                    self.opened_at = None
                    logger.info(
                        f"circuit_breaker.{self.name}.closed",
                        extra={
                            "state_change": "half_open -> closed",
                            "consecutive_successes": self.success_count,
                        },
                    )
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.failure_count = 0
                self.last_failure_time = None

    async def _on_failure(self, exc: Exception):
        """Handle failed call."""
        async with self._lock:
            now = time.time()
            self.last_failure_time = now

            # Only count certain failures (not client errors like 400, 404)
            if self._should_count_failure(exc):
                self.failure_count += 1

                if self.state == CircuitState.HALF_OPEN:
                    # Failure in half-open immediately reopens circuit
                    self.state = CircuitState.OPEN
                    self.opened_at = now
                    logger.warning(
                        f"circuit_breaker.{self.name}.reopened",
                        extra={
                            "state_change": "half_open -> open",
                            "error": str(exc),
                        },
                    )
                elif (
                    self.state == CircuitState.CLOSED
                    and self.failure_count >= self.config.failure_threshold
                ):
                    # Too many failures, open circuit
                    self.state = CircuitState.OPEN
                    self.opened_at = now
                    logger.error(
                        f"circuit_breaker.{self.name}.opened",
                        extra={
                            "state_change": "closed -> open",
                            "failure_count": self.failure_count,
                            "threshold": self.config.failure_threshold,
                            "error": str(exc),
                        },
                    )

    def _should_count_failure(self, exc: Exception) -> bool:
        """
        Determine if exception should count toward circuit breaker threshold.

        Only server errors (5xx) and timeouts count. Client errors (4xx)
        don't indicate service health issues.
        """
        if isinstance(exc, httpx.HTTPStatusError):
            # Only count server errors and rate limits
            return exc.response.status_code >= 500 or exc.response.status_code == 429
        if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
            return True
        if isinstance(exc, asyncio.TimeoutError):
            return True
        return False

    async def reset(self):
        """Manually reset circuit breaker to closed state."""
        async with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            self.opened_at = None
        logger.info(f"circuit_breaker.{self.name}.reset", extra={"state": "closed"})


@dataclass
class RateLimitInfo:
    """Information about rate limiting from service."""

    retry_after_seconds: Optional[float] = None
    limit: Optional[int] = None
    remaining: Optional[int] = None
    reset_at: Optional[float] = None


def extract_rate_limit_info(response) -> RateLimitInfo:
    """
    Extract rate limit information from HTTP response headers.

    Parameters
    ----------
    response : httpx.Response
        HTTP response object

    Returns
    -------
    RateLimitInfo
        Parsed rate limit information
    """
    if not isinstance(response, httpx.Response):
        return RateLimitInfo()

    headers = response.headers

    # Parse Retry-After header (seconds or HTTP date)
    retry_after = None
    if "retry-after" in headers:
        retry_value = headers["retry-after"]
        try:
            # Try as integer seconds
            retry_after = float(retry_value)
        except ValueError:
            # Try as HTTP date
            try:
                retry_date = parsedate_to_datetime(retry_value)
                retry_after = retry_date.timestamp() - time.time()
            except Exception:
                logger.warning(
                    "rate_limit.parse_retry_after_failed",
                    extra={"value": retry_value},
                )

    # Parse X-RateLimit-* headers (common standard)
    limit = None
    if "x-ratelimit-limit" in headers:
        try:
            limit = int(headers["x-ratelimit-limit"])
        except ValueError:
            pass

    remaining = None
    if "x-ratelimit-remaining" in headers:
        try:
            remaining = int(headers["x-ratelimit-remaining"])
        except ValueError:
            pass

    reset_at = None
    if "x-ratelimit-reset" in headers:
        try:
            reset_at = float(headers["x-ratelimit-reset"])
        except ValueError:
            pass

    return RateLimitInfo(
        retry_after_seconds=retry_after,
        limit=limit,
        remaining=remaining,
        reset_at=reset_at,
    )


class RequestQueue:  # pylint: disable=too-few-public-methods
    """
    Async request queue for backpressure management.

    Limits concurrent requests and queues excess requests
    until capacity is available.
    """

    def __init__(self, max_concurrent: int = 10, max_queue_size: int = 100):
        """
        Initialize request queue.

        Parameters
        ----------
        max_concurrent : int
            Maximum number of concurrent requests
        max_queue_size : int
            Maximum number of queued requests (blocks if exceeded)
        """
        self.max_concurrent = max_concurrent
        self.max_queue_size = max_queue_size
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._queue_size = 0
        self._lock = asyncio.Lock()

    async def execute(self, func, *args, **kwargs):
        """
        Execute function with backpressure management.

        Parameters
        ----------
        func : callable
            Async function to execute
        *args, **kwargs
            Arguments to pass to function

        Returns
        -------
        Any
            Result from function

        Raises
        ------
        RuntimeError
            If queue is full (backpressure limit exceeded)
        """
        async with self._lock:
            if self._queue_size >= self.max_queue_size:
                raise RuntimeError(
                    f"Request queue full ({self.max_queue_size} requests queued). "
                    "System is under heavy load - try again later."
                )
            self._queue_size += 1

        try:
            async with self._semaphore:
                async with self._lock:
                    self._queue_size -= 1
                return await func(*args, **kwargs)
        except Exception:
            async with self._lock:
                self._queue_size -= 1
            raise
