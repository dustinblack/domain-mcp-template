"""
Tests for backpressure and rate limiting utilities.
"""

import asyncio
import time
from unittest.mock import MagicMock

import httpx
import pytest

from src.utils.backpressure import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    RequestQueue,
    extract_rate_limit_info,
)


@pytest.mark.asyncio
async def test_circuit_breaker_normal_operation():
    """Test circuit breaker in normal closed state."""
    cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))

    async def success_func():
        return "success"

    result = await cb.call(success_func)
    assert result == "success"
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_opens_on_failures():
    """Test circuit opens after failure threshold."""
    cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))

    async def failing_func():
        # Simulate 503 error
        response = MagicMock()
        response.status_code = 503
        raise httpx.HTTPStatusError("error", request=MagicMock(), response=response)

    # First 2 failures, circuit stays closed
    for i in range(2):
        with pytest.raises(httpx.HTTPStatusError):
            await cb.call(failing_func)
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == i + 1

    # 3rd failure opens circuit
    with pytest.raises(httpx.HTTPStatusError):
        await cb.call(failing_func)
    assert cb.state == CircuitState.OPEN
    assert cb.failure_count == 3


@pytest.mark.asyncio
async def test_circuit_breaker_blocks_when_open():
    """Test circuit blocks requests when open."""
    cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=1))

    async def failing_func():
        response = MagicMock()
        response.status_code = 503
        raise httpx.HTTPStatusError("error", request=MagicMock(), response=response)

    # Open the circuit
    with pytest.raises(httpx.HTTPStatusError):
        await cb.call(failing_func)
    assert cb.state == CircuitState.OPEN

    # Subsequent calls should be blocked
    async def success_func():
        return "success"

    with pytest.raises(RuntimeError, match="Circuit breaker .* is OPEN"):
        await cb.call(success_func)


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_recovery():
    """Test circuit transitions to half-open and recovers."""
    cb = CircuitBreaker(
        "test",
        CircuitBreakerConfig(
            failure_threshold=1, success_threshold=2, timeout_seconds=0.1
        ),
    )

    async def failing_func():
        response = MagicMock()
        response.status_code = 503
        raise httpx.HTTPStatusError("error", request=MagicMock(), response=response)

    # Open the circuit
    with pytest.raises(httpx.HTTPStatusError):
        await cb.call(failing_func)
    assert cb.state == CircuitState.OPEN

    # Wait for timeout to transition to half-open
    await asyncio.sleep(0.15)

    async def success_func():
        return "success"

    # First success in half-open
    result = await cb.call(success_func)
    assert result == "success"
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.success_count == 1

    # Second success closes circuit
    result = await cb.call(success_func)
    assert result == "success"
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_failure_reopens():
    """Test failure in half-open immediately reopens circuit."""
    cb = CircuitBreaker(
        "test", CircuitBreakerConfig(failure_threshold=1, timeout_seconds=0.1)
    )

    async def failing_func():
        response = MagicMock()
        response.status_code = 503
        raise httpx.HTTPStatusError("error", request=MagicMock(), response=response)

    # Open the circuit
    with pytest.raises(httpx.HTTPStatusError):
        await cb.call(failing_func)
    assert cb.state == CircuitState.OPEN

    # Wait for half-open transition
    await asyncio.sleep(0.15)

    # Failure in half-open reopens
    with pytest.raises(httpx.HTTPStatusError):
        await cb.call(failing_func)
    assert cb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_ignores_client_errors():
    """Test circuit breaker doesn't count 4xx errors."""
    cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2))

    async def client_error_func():
        response = MagicMock()
        response.status_code = 404
        raise httpx.HTTPStatusError("not found", request=MagicMock(), response=response)

    # Multiple 404s should NOT open circuit
    for _ in range(5):
        with pytest.raises(httpx.HTTPStatusError):
            await cb.call(client_error_func)
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0  # Client errors not counted


@pytest.mark.asyncio
async def test_circuit_breaker_counts_timeouts():
    """Test circuit breaker counts timeout errors."""
    cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2))

    async def timeout_func():
        raise asyncio.TimeoutError("timed out")

    # First timeout
    with pytest.raises(asyncio.TimeoutError):
        await cb.call(timeout_func)
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 1

    # Second timeout opens circuit
    with pytest.raises(asyncio.TimeoutError):
        await cb.call(timeout_func)
    assert cb.state == CircuitState.OPEN
    assert cb.failure_count == 2


@pytest.mark.asyncio
async def test_circuit_breaker_counts_rate_limits():
    """Test circuit breaker counts 429 rate limit errors."""
    cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2))

    async def rate_limit_func():
        response = MagicMock()
        response.status_code = 429
        raise httpx.HTTPStatusError(
            "rate limited", request=MagicMock(), response=response
        )

    # Rate limits count toward threshold
    with pytest.raises(httpx.HTTPStatusError):
        await cb.call(rate_limit_func)
    assert cb.failure_count == 1

    with pytest.raises(httpx.HTTPStatusError):
        await cb.call(rate_limit_func)
    assert cb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_reset():
    """Test manual circuit breaker reset."""
    cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=1))

    async def failing_func():
        response = MagicMock()
        response.status_code = 503
        raise httpx.HTTPStatusError("error", request=MagicMock(), response=response)

    # Open the circuit
    with pytest.raises(httpx.HTTPStatusError):
        await cb.call(failing_func)
    assert cb.state == CircuitState.OPEN

    # Reset
    await cb.reset()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0

    # Should work now
    async def success_func():
        return "success"

    result = await cb.call(success_func)
    assert result == "success"


def test_extract_rate_limit_info_retry_after_seconds():
    """Test extracting Retry-After header as seconds."""
    response = MagicMock(spec=httpx.Response)
    response.headers = {"retry-after": "60"}

    info = extract_rate_limit_info(response)
    assert info.retry_after_seconds == 60.0


def test_extract_rate_limit_info_x_ratelimit_headers():
    """Test extracting X-RateLimit-* headers."""
    response = MagicMock(spec=httpx.Response)
    response.headers = {
        "x-ratelimit-limit": "100",
        "x-ratelimit-remaining": "45",
        "x-ratelimit-reset": "1697500000",
    }

    info = extract_rate_limit_info(response)
    assert info.limit == 100
    assert info.remaining == 45
    assert info.reset_at == 1697500000.0


def test_extract_rate_limit_info_missing_headers():
    """Test extraction with missing headers."""
    response = MagicMock(spec=httpx.Response)
    response.headers = {}

    info = extract_rate_limit_info(response)
    assert info.retry_after_seconds is None
    assert info.limit is None
    assert info.remaining is None
    assert info.reset_at is None


def test_extract_rate_limit_info_invalid_response():
    """Test extraction with non-Response object."""
    info = extract_rate_limit_info("not a response")
    assert info.retry_after_seconds is None


@pytest.mark.asyncio
async def test_request_queue_normal_operation():
    """Test request queue allows concurrent requests."""
    queue = RequestQueue(max_concurrent=2)

    call_times = []

    async def slow_func(duration: float):
        start = time.time()
        await asyncio.sleep(duration)
        call_times.append(time.time() - start)
        return "done"

    # Launch 2 concurrent requests
    tasks = [queue.execute(slow_func, 0.1) for _ in range(2)]
    results = await asyncio.gather(*tasks)

    assert all(r == "done" for r in results)
    # Both should have run concurrently (~0.1s each, not 0.2s total)
    assert all(0.05 < t < 0.15 for t in call_times)


@pytest.mark.asyncio
async def test_request_queue_enforces_concurrency_limit():
    """Test request queue enforces max concurrent limit."""
    queue = RequestQueue(max_concurrent=1)

    call_order = []

    async def ordered_func(order: int):
        call_order.append(f"start_{order}")
        await asyncio.sleep(0.05)
        call_order.append(f"end_{order}")
        return order

    # Launch 3 requests (only 1 can run at a time)
    tasks = [queue.execute(ordered_func, i) for i in range(3)]
    results = await asyncio.gather(*tasks)

    assert results == [0, 1, 2]
    # Should run sequentially
    assert call_order == [
        "start_0",
        "end_0",
        "start_1",
        "end_1",
        "start_2",
        "end_2",
    ]


@pytest.mark.asyncio
async def test_request_queue_blocks_when_full():
    """Test request queue blocks when max queue size exceeded."""
    queue = RequestQueue(max_concurrent=1, max_queue_size=2)

    async def slow_func():
        await asyncio.sleep(1.0)  # Very slow
        return "done"

    # Start 1 request (fills concurrent slot)
    task1 = asyncio.create_task(queue.execute(slow_func))

    # Add 2 more to queue (fills queue)
    task2 = asyncio.create_task(queue.execute(slow_func))
    task3 = asyncio.create_task(queue.execute(slow_func))

    await asyncio.sleep(0.01)  # Let tasks queue

    # 4th request should be rejected
    with pytest.raises(RuntimeError, match="Request queue full"):
        await queue.execute(slow_func)

    # Cancel tasks to avoid hanging test
    task1.cancel()
    task2.cancel()
    task3.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task1
    with pytest.raises(asyncio.CancelledError):
        await task2
    with pytest.raises(asyncio.CancelledError):
        await task3


@pytest.mark.asyncio
async def test_request_queue_handles_errors():
    """Test request queue properly handles exceptions."""
    queue = RequestQueue(max_concurrent=2)

    async def failing_func():
        raise ValueError("test error")

    with pytest.raises(ValueError, match="test error"):
        await queue.execute(failing_func)

    # Queue should still work after error
    async def success_func():
        return "success"

    result = await queue.execute(success_func)
    assert result == "success"
