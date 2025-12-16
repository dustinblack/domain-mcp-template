"""Rate limiting for API endpoints.

Provides per-client rate limiting and token budget tracking for LLM endpoints.
"""

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_hour: int = 100
    tokens_per_hour: int = 100000
    window_size_seconds: int = 3600
    enable_rate_limiting: bool = True
    admin_bypass_key: Optional[str] = None


@dataclass
class RateLimitState:
    """Tracks rate limit state for a client."""

    request_timestamps: deque  # timestamps of recent requests
    token_usage: deque  # (timestamp, token_count) tuples


class RateLimiter:
    """In-memory rate limiter with sliding window.

    Tracks per-client request counts and token usage over time windows.
    """

    def __init__(self, config: RateLimitConfig):
        """Initialize rate limiter.

        Args:
            config: Rate limiting configuration.
        """
        self.config = config
        self.clients: Dict[str, RateLimitState] = defaultdict(
            lambda: RateLimitState(request_timestamps=deque(), token_usage=deque())
        )
        logger.info(
            "Rate limiter initialized",
            extra={
                "requests_per_hour": config.requests_per_hour,
                "tokens_per_hour": config.tokens_per_hour,
                "enabled": config.enable_rate_limiting,
            },
        )

    def check_rate_limit(
        self, client_id: str, admin_key: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Check if client has exceeded rate limits.

        Args:
            client_id: Unique identifier for the client
                (IP address, user ID, API key).
            admin_key: Optional admin bypass key.

        Returns:
            Tuple of (allowed: bool, error_message: Optional[str]).
            If allowed=False, error_message explains the limit exceeded.
        """
        # Admin bypass
        if (
            admin_key
            and self.config.admin_bypass_key
            and admin_key == self.config.admin_bypass_key
        ):
            logger.debug("Admin bypass used", extra={"client_id": client_id})
            return True, None

        # Rate limiting disabled
        if not self.config.enable_rate_limiting:
            return True, None

        state = self.clients[client_id]
        now = time.time()
        window_start = now - self.config.window_size_seconds

        # Clean old timestamps
        self._clean_old_entries(state, window_start)

        # Check request limit
        request_count = len(state.request_timestamps)
        if request_count >= self.config.requests_per_hour:
            retry_after = int(
                state.request_timestamps[0] + self.config.window_size_seconds - now
            )
            logger.warning(
                "Request rate limit exceeded",
                extra={
                    "client_id": client_id,
                    "requests": request_count,
                    "limit": self.config.requests_per_hour,
                    "retry_after_seconds": retry_after,
                },
            )
            return (
                False,
                f"Request rate limit exceeded ({self.config.requests_per_hour}"
                f" requests/hour). Retry after {retry_after} seconds.",
            )

        # Check token limit
        token_count = sum(tokens for _, tokens in state.token_usage)
        if token_count >= self.config.tokens_per_hour:
            retry_after = int(
                state.token_usage[0][0] + self.config.window_size_seconds - now
            )
            logger.warning(
                "Token budget exceeded",
                extra={
                    "client_id": client_id,
                    "tokens": token_count,
                    "limit": self.config.tokens_per_hour,
                    "retry_after_seconds": retry_after,
                },
            )
            return (
                False,
                f"Token budget exceeded ({self.config.tokens_per_hour} "
                f"tokens/hour). Retry after {retry_after} seconds.",
            )

        return True, None

    def record_request(self, client_id: str, tokens_used: Optional[int] = None) -> None:
        """Record a request and token usage for a client.

        Args:
            client_id: Unique identifier for the client.
            tokens_used: Number of tokens consumed (prompt + completion).
        """
        state = self.clients[client_id]
        now = time.time()

        # Record request timestamp
        state.request_timestamps.append(now)

        # Record token usage
        if tokens_used is not None and tokens_used > 0:
            state.token_usage.append((now, tokens_used))

        logger.debug(
            "Request recorded",
            extra={
                "client_id": client_id,
                "tokens_used": tokens_used,
                "total_requests": len(state.request_timestamps),
                "total_tokens": sum(tokens for _, tokens in state.token_usage),
            },
        )

    def get_client_stats(self, client_id: str) -> Dict:
        """Get current usage stats for a client.

        Args:
            client_id: Unique identifier for the client.

        Returns:
            Dictionary with usage statistics.
        """
        state = self.clients[client_id]
        now = time.time()
        window_start = now - self.config.window_size_seconds

        # Clean old entries
        self._clean_old_entries(state, window_start)

        request_count = len(state.request_timestamps)
        token_count = sum(tokens for _, tokens in state.token_usage)

        return {
            "client_id": client_id,
            "requests_remaining": max(0, self.config.requests_per_hour - request_count),
            "requests_limit": self.config.requests_per_hour,
            "tokens_remaining": max(0, self.config.tokens_per_hour - token_count),
            "tokens_limit": self.config.tokens_per_hour,
            "window_seconds": self.config.window_size_seconds,
        }

    def _clean_old_entries(self, state: RateLimitState, window_start: float) -> None:
        """Remove entries older than the time window.

        Args:
            state: Client rate limit state.
            window_start: Timestamp marking the start of the window.
        """
        # Remove old request timestamps
        while state.request_timestamps and state.request_timestamps[0] < window_start:
            state.request_timestamps.popleft()

        # Remove old token usage
        while state.token_usage and state.token_usage[0][0] < window_start:
            state.token_usage.popleft()
