"""
Tests for partial results handling utilities.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.utils.partial_results import (
    FailureInfo,
    PartialResult,
    fetch_datasets_with_fallback,
    format_failure_summary,
    gather_partial,
)


@pytest.mark.asyncio
async def test_gather_partial_all_succeed():
    """Test gathering when all operations succeed."""

    async def success_op(value):
        await asyncio.sleep(0.01)
        return value

    operations = {
        "op1": success_op("result1"),
        "op2": success_op("result2"),
        "op3": success_op("result3"),
    }

    result = await gather_partial(operations, "test_operation")

    assert result.all_succeeded
    assert not result.has_failures
    assert len(result.successes) == 3
    assert len(result.failures) == 0
    assert result.success_rate == 1.0
    assert set(result.successes) == {"result1", "result2", "result3"}


@pytest.mark.asyncio
async def test_gather_partial_some_fail():
    """Test gathering when some operations fail."""

    async def success_op(value):
        return value

    async def fail_op(msg):
        raise ValueError(msg)

    operations = {
        "op1": success_op("result1"),
        "op2": fail_op("error in op2"),
        "op3": success_op("result3"),
        "op4": fail_op("error in op4"),
    }

    result = await gather_partial(operations, "test_operation")

    assert result.has_failures
    assert not result.all_succeeded
    assert not result.all_failed
    assert len(result.successes) == 2
    assert len(result.failures) == 2
    assert result.success_rate == 0.5
    assert set(result.successes) == {"result1", "result3"}

    # Check failure info
    failed_ids = {f.identifier for f in result.failures}
    assert failed_ids == {"op2", "op4"}
    assert all(f.error_type == "parse_error" for f in result.failures)


@pytest.mark.asyncio
async def test_gather_partial_all_fail():
    """Test gathering when all operations fail."""

    async def fail_op(msg):
        raise ValueError(msg)

    operations = {
        "op1": fail_op("error1"),
        "op2": fail_op("error2"),
    }

    result = await gather_partial(operations, "test_operation")

    assert result.all_failed
    assert result.has_failures
    assert not result.all_succeeded
    assert len(result.successes) == 0
    assert len(result.failures) == 2
    assert result.success_rate == 0.0


@pytest.mark.asyncio
async def test_gather_partial_min_success_rate_met():
    """Test that min_success_rate threshold is enforced (met)."""

    async def success_op():
        return "success"

    async def fail_op():
        raise ValueError("error")

    operations = {
        "op1": success_op(),
        "op2": success_op(),
        "op3": fail_op(),
    }

    # 2/3 = 66.7% success rate, should pass 50% threshold
    result = await gather_partial(operations, "test", min_success_rate=0.5)
    assert result.success_rate >= 0.5


@pytest.mark.asyncio
async def test_gather_partial_min_success_rate_not_met():
    """Test that min_success_rate threshold raises error when not met."""

    async def success_op():
        return "success"

    async def fail_op():
        raise ValueError("error")

    operations = {
        "op1": success_op(),
        "op2": fail_op(),
        "op3": fail_op(),
        "op4": fail_op(),
    }

    # 1/4 = 25% success rate, should fail 50% threshold
    with pytest.raises(RuntimeError, match="Success rate .* below minimum"):
        await gather_partial(operations, "test", min_success_rate=0.5)


@pytest.mark.asyncio
async def test_gather_partial_empty_operations():
    """Test that empty operations dict raises ValueError."""
    with pytest.raises(ValueError, match="operations dictionary cannot be empty"):
        await gather_partial({}, "test")


@pytest.mark.asyncio
async def test_gather_partial_classifies_http_errors():
    """Test that different HTTP errors are classified correctly."""

    async def timeout_error():
        raise httpx.TimeoutException("timeout")

    async def server_error():
        response = MagicMock()
        response.status_code = 503
        raise httpx.HTTPStatusError(
            "server error", request=MagicMock(), response=response
        )

    async def not_found():
        response = MagicMock()
        response.status_code = 404
        raise httpx.HTTPStatusError("not found", request=MagicMock(), response=response)

    async def rate_limit():
        response = MagicMock()
        response.status_code = 429
        raise httpx.HTTPStatusError(
            "rate limit", request=MagicMock(), response=response
        )

    operations = {
        "timeout": timeout_error(),
        "server": server_error(),
        "notfound": not_found(),
        "ratelimit": rate_limit(),
    }

    result = await gather_partial(operations, "test")

    assert result.all_failed
    failures_by_id = {f.identifier: f for f in result.failures}

    assert failures_by_id["timeout"].error_type == "timeout"
    assert failures_by_id["timeout"].retryable is True

    assert failures_by_id["server"].error_type == "server_error"
    assert failures_by_id["server"].retryable is True

    assert failures_by_id["notfound"].error_type == "not_found"
    assert failures_by_id["notfound"].retryable is False

    assert failures_by_id["ratelimit"].error_type == "rate_limit"
    assert failures_by_id["ratelimit"].retryable is True


@pytest.mark.asyncio
async def test_fetch_datasets_with_fallback_all_succeed():
    """Test fetching datasets when all succeed."""
    mock_adapter = AsyncMock()

    # Mock successful responses
    def get_dataset(request):
        return AsyncMock(content={"id": request.dataset_id, "data": "test"})

    mock_adapter.datasets_get.side_effect = get_dataset

    result = await fetch_datasets_with_fallback(
        mock_adapter, ["ds1", "ds2", "ds3"], min_success_rate=0.5
    )

    assert result.all_succeeded
    assert len(result.successes) == 3
    assert mock_adapter.datasets_get.call_count == 3


@pytest.mark.asyncio
async def test_fetch_datasets_with_fallback_some_fail():
    """Test fetching datasets when some fail."""
    mock_adapter = AsyncMock()

    call_count = 0

    async def get_dataset(request):
        nonlocal call_count
        call_count += 1
        if request.dataset_id == "ds2":
            raise httpx.HTTPStatusError(
                "error", request=MagicMock(), response=MagicMock(status_code=503)
            )
        return AsyncMock(content={"id": request.dataset_id, "data": "test"})

    mock_adapter.datasets_get.side_effect = get_dataset

    result = await fetch_datasets_with_fallback(
        mock_adapter, ["ds1", "ds2", "ds3"], min_success_rate=0.5
    )

    assert result.has_failures
    assert len(result.successes) == 2
    assert len(result.failures) == 1
    assert result.failures[0].identifier == "ds2"
    assert result.success_rate >= 0.5


@pytest.mark.asyncio
async def test_fetch_datasets_with_fallback_below_threshold():
    """Test fetching datasets when below min_success_rate."""
    mock_adapter = AsyncMock()

    async def get_dataset(request):
        if request.dataset_id != "ds1":
            raise ValueError("error")
        return AsyncMock(content={"id": request.dataset_id})

    mock_adapter.datasets_get.side_effect = get_dataset

    # 1/3 = 33% < 50% threshold
    with pytest.raises(RuntimeError, match="Success rate .* below minimum"):
        await fetch_datasets_with_fallback(
            mock_adapter, ["ds1", "ds2", "ds3"], min_success_rate=0.5
        )


@pytest.mark.asyncio
async def test_fetch_datasets_with_fallback_list_content():
    """Test fetching datasets when content is a list."""
    mock_adapter = AsyncMock()

    async def get_dataset(request):
        # Horreum sometimes returns content as a list
        return AsyncMock(
            content=[
                {"id": f"{request.dataset_id}_item1"},
                {"id": f"{request.dataset_id}_item2"},
            ]
        )

    mock_adapter.datasets_get.side_effect = get_dataset

    result = await fetch_datasets_with_fallback(mock_adapter, ["ds1", "ds2"])

    # 2 datasets × 2 items each = 4 total items
    assert len(result.successes) == 4


def test_format_failure_summary_no_failures():
    """Test formatting summary when no failures."""
    result = PartialResult(successes=["a", "b", "c"], failures=[])
    summary = format_failure_summary(result, "test")
    assert "All 3 test(s) succeeded" in summary


def test_format_failure_summary_with_failures():
    """Test formatting summary with failures."""
    result = PartialResult(
        successes=["a", "b"],
        failures=[
            FailureInfo("id1", "error1", "timeout", retryable=True),
            FailureInfo("id2", "error2", "timeout", retryable=True),
            FailureInfo("id3", "error3", "not_found", retryable=False),
        ],
    )
    summary = format_failure_summary(result, "dataset")

    assert "2 succeeded, 3 failed" in summary
    assert "40.0% success rate" in summary or "40% success rate" in summary
    assert "2 timeout (retryable)" in summary
    assert "1 not_found (not retryable)" in summary
    assert "id1" in summary


def test_format_failure_summary_many_failures():
    """Test formatting summary with many failures (truncation)."""
    failures = [
        FailureInfo(f"id{i}", f"error{i}", "server_error", retryable=True)
        for i in range(10)
    ]
    result = PartialResult(successes=[], failures=failures)
    summary = format_failure_summary(result)

    # Should show first 3 and indicate more
    assert "id0" in summary
    assert "id1" in summary
    assert "id2" in summary
    assert "... and 7 more" in summary


def test_partial_result_properties():
    """Test PartialResult computed properties."""
    # Empty result
    empty = PartialResult()
    assert empty.success_rate == 0.0
    assert not empty.has_failures
    assert not empty.all_succeeded
    assert not empty.all_failed

    # All succeeded
    all_success = PartialResult(successes=["a", "b"])
    assert all_success.success_rate == 1.0
    assert not all_success.has_failures
    assert all_success.all_succeeded
    assert not all_success.all_failed

    # All failed
    all_fail = PartialResult(
        failures=[
            FailureInfo("id1", "e1", "error"),
            FailureInfo("id2", "e2", "error"),
        ]
    )
    assert all_fail.success_rate == 0.0
    assert all_fail.has_failures
    assert not all_fail.all_succeeded
    assert all_fail.all_failed

    # Mixed
    mixed = PartialResult(
        successes=["a"],
        failures=[FailureInfo("id1", "e1", "error")],
    )
    assert mixed.success_rate == 0.5
    assert mixed.has_failures
    assert not mixed.all_succeeded
    assert not mixed.all_failed
