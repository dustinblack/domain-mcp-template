"""
Partial results handling for aggregating data when some operations fail.

Provides utilities for collecting successful results while tracking failures,
ensuring users get as much data as possible even when some sources fail.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Dict, List, TypeVar

import httpx

from src.schemas.source_mcp_contract import DatasetsGetRequest

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class PartialResult:
    """
    Result container for operations that may partially fail.

    Attributes
    ----------
    successes : List[T]
        Successfully retrieved items
    failures : List[FailureInfo]
        Information about failed operations
    success_rate : float
        Ratio of successes to total attempts (0.0-1.0)
    """

    successes: List[Any] = field(default_factory=list)
    failures: List["FailureInfo"] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0.0-1.0)."""
        total = len(self.successes) + len(self.failures)
        if total == 0:
            return 0.0
        return len(self.successes) / total

    @property
    def has_failures(self) -> bool:
        """Check if any operations failed."""
        return len(self.failures) > 0

    @property
    def all_succeeded(self) -> bool:
        """Check if all operations succeeded."""
        return len(self.failures) == 0 and len(self.successes) > 0

    @property
    def all_failed(self) -> bool:
        """Check if all operations failed."""
        return len(self.successes) == 0 and len(self.failures) > 0


@dataclass
class FailureInfo:
    """
    Information about a failed operation.

    Attributes
    ----------
    identifier : str
        Identifier for the failed operation (e.g., dataset_id)
    error : str
        Error message
    error_type : str
        Type of error (e.g., "http_error", "timeout", "parse_error")
    retryable : bool
        Whether the operation might succeed if retried
    """

    identifier: str
    error: str
    error_type: str
    retryable: bool = False


async def gather_partial(
    operations: Dict[str, Awaitable[T]],
    operation_type: str = "operation",
    min_success_rate: float = 0.0,
) -> PartialResult:
    """
    Execute multiple async operations and collect partial results.

    Continues execution even if some operations fail, returning all
    successful results along with failure information.

    Parameters
    ----------
    operations : Dict[str, Awaitable[T]]
        Dictionary mapping identifiers to async operations
    operation_type : str
        Human-readable type of operation (for logging)
    min_success_rate : float
        Minimum required success rate (0.0-1.0). If not met, raises RuntimeError.

    Returns
    -------
    PartialResult
        Container with successes and failures

    Raises
    ------
    RuntimeError
        If success rate is below min_success_rate
    ValueError
        If operations dict is empty

    Examples
    --------
    >>> operations = {
    ...     "dataset_1": fetch_dataset("1"),
    ...     "dataset_2": fetch_dataset("2"),
    ...     "dataset_3": fetch_dataset("3"),
    ... }
    >>> result = await gather_partial(operations, "dataset fetch")
    >>> print(f"Got {len(result.successes)} datasets, {len(result.failures)} failed")
    """
    if not operations:
        raise ValueError("operations dictionary cannot be empty")

    results = PartialResult()

    # Create tasks with identifiers
    tasks: Dict[str, "asyncio.Task[Any]"] = {
        identifier: asyncio.create_task(operation)  # type: ignore[arg-type]
        for identifier, operation in operations.items()
    }

    # Wait for all to complete (including failures)
    completed = await asyncio.gather(*tasks.values(), return_exceptions=True)

    # Process results
    for identifier, result in zip(tasks.keys(), completed):
        if isinstance(result, Exception):
            # Operation failed
            error_type = _classify_error(result)
            retryable = _is_retryable(error_type)

            failure = FailureInfo(
                identifier=identifier,
                error=str(result),
                error_type=error_type,
                retryable=retryable,
            )
            results.failures.append(failure)

            logger.warning(
                f"partial_results.{operation_type}.failed",
                extra={
                    "identifier": identifier,
                    "error_type": error_type,
                    "retryable": retryable,
                    "error": str(result),
                },
            )
        else:
            # Operation succeeded
            results.successes.append(result)

    # Log summary
    logger.info(
        f"partial_results.{operation_type}.complete",
        extra={
            "total": len(operations),
            "successes": len(results.successes),
            "failures": len(results.failures),
            "success_rate": results.success_rate,
        },
    )

    # Check minimum success rate
    if results.success_rate < min_success_rate:
        raise RuntimeError(
            f"Success rate {results.success_rate:.1%} below minimum "
            f"{min_success_rate:.1%} for {operation_type}. "
            f"Got {len(results.successes)} successes, {len(results.failures)} failures."
        )

    return results


def _classify_error(exc: Exception) -> str:
    """Classify exception into error type."""
    error_type = "unknown_error"

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status >= 500:
            error_type = "server_error"
        elif status == 429:
            error_type = "rate_limit"
        elif status in (401, 403):
            error_type = "auth_error"
        elif status == 404:
            error_type = "not_found"
        else:
            error_type = "http_error"
    elif isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError)):
        error_type = "timeout"
    elif isinstance(exc, httpx.ConnectError):
        error_type = "connection_error"
    elif isinstance(exc, ValueError):
        error_type = "parse_error"
    elif isinstance(exc, KeyError):
        error_type = "missing_field"

    return error_type


def _is_retryable(error_type: str) -> bool:
    """Determine if an error type is retryable."""
    retryable_types = {
        "timeout",
        "connection_error",
        "server_error",
        "rate_limit",
    }
    return error_type in retryable_types


async def fetch_datasets_with_fallback(
    adapter: Any,
    dataset_ids: List[str],
    min_success_rate: float = 0.5,
) -> PartialResult:
    """
    Fetch multiple datasets with partial results handling.

    Parameters
    ----------
    adapter : Any
        Source adapter with datasets_get method
    dataset_ids : List[str]
        List of dataset IDs to fetch
    min_success_rate : float
        Minimum required success rate (default 0.5 = 50%)

    Returns
    -------
    PartialResult
        Container with successful dataset contents and failure info
    """
    operations = {
        dataset_id: adapter.datasets_get(
            DatasetsGetRequest.model_validate(
                {
                    "dataset_id": dataset_id,
                    "if_none_match": None,
                    "if_modified_since": None,
                }
            )
        )
        for dataset_id in dataset_ids
    }

    result = await gather_partial(
        operations,
        operation_type="dataset_fetch",
        min_success_rate=min_success_rate,
    )

    # Extract content from responses
    contents: List[Dict[str, Any]] = []
    for response in result.successes:
        if isinstance(response.content, dict):
            contents.append(response.content)
        elif isinstance(response.content, list):
            for item in response.content:
                if isinstance(item, dict):
                    contents.append(item)

    # Return new PartialResult with contents instead of responses
    return PartialResult(successes=contents, failures=result.failures)


def format_failure_summary(
    result: PartialResult, operation_type: str = "operation"
) -> str:
    """
    Format a human-readable summary of partial result failures.

    Parameters
    ----------
    result : PartialResult
        The partial result to summarize
    operation_type : str
        Type of operation (for messaging)

    Returns
    -------
    str
        Formatted summary string
    """
    if not result.has_failures:
        return f"All {len(result.successes)} {operation_type}(s) succeeded."

    lines = [
        f"Partial results: {len(result.successes)} succeeded, "
        f"{len(result.failures)} failed ({result.success_rate:.1%} success rate)",
    ]

    # Group failures by type
    failures_by_type: Dict[str, List[FailureInfo]] = {}
    for failure in result.failures:
        failures_by_type.setdefault(failure.error_type, []).append(failure)

    for error_type, failures in failures_by_type.items():
        count = len(failures)
        retryable = failures[0].retryable
        retry_note = " (retryable)" if retryable else " (not retryable)"
        lines.append(f"  - {count} {error_type}{retry_note}")

        # Show first few identifiers
        identifiers = [f.identifier for f in failures[:3]]
        if len(failures) > 3:
            identifiers.append(f"... and {len(failures) - 3} more")
        lines.append(f"    Affected: {', '.join(identifiers)}")

    return "\n".join(lines)
