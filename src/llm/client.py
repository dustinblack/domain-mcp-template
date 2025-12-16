"""LLM client for multiple providers (Gemini primary).

Provides a unified interface for interacting with various LLM APIs, with
Google Gemini as the primary provider. Supports both streaming and non-streaming
completion modes, token usage tracking, and error handling.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LlmMessage:
    """Message in an LLM conversation."""

    role: str  # "user", "assistant", or "system"
    content: str


@dataclass
class LlmRequest:
    """Request to the LLM API."""

    messages: List[LlmMessage]
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


@dataclass
class LlmResponse:
    """Response from the LLM API."""

    content: str
    usage: Optional[Dict[str, int]] = None  # prompt_tokens, completion_tokens, total


StreamCallback = Callable[[str], None]


class LlmClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def complete(self, request: LlmRequest) -> LlmResponse:
        """Generate a completion for the given request.

        Args:
            request: The LLM request with messages and parameters.

        Returns:
            LlmResponse with generated content and usage statistics.
        """
        pass

    async def complete_stream(
        self, request: LlmRequest, callback: StreamCallback
    ) -> None:
        """Generate a streaming completion (optional).

        Args:
            request: The LLM request with messages and parameters.
            callback: Function called with each content chunk.

        Raises:
            NotImplementedError: If streaming is not supported.
        """
        raise NotImplementedError(
            f"Streaming not supported by {self.__class__.__name__}"
        )


class GeminiClient(LlmClient):
    """Google Gemini API client.

    Supports both public Gemini API (generativelanguage.googleapis.com) and
    corporate/Vertex AI endpoints. Provides non-streaming and streaming
    completion modes with token usage tracking.

    Example:
        client = GeminiClient(
            api_key="your-api-key",
            model="gemini-1.5-pro",
            endpoint="https://generativelanguage.googleapis.com/v1beta"
        )
        response = await client.complete(LlmRequest(
            messages=[LlmMessage(role="user", content="Hello")]
        ))
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        endpoint: Optional[str] = None,
        project_id: Optional[str] = None,
    ):
        """Initialize Gemini client.

        Args:
            api_key: Google API key for authentication.
            model: Model name (e.g., "gemini-1.5-pro", "gemini-2.0-flash-exp").
            endpoint: Optional custom endpoint for Vertex AI / corporate instances.
                Defaults to public Gemini API.
            project_id: Optional Google Cloud project ID (for Vertex AI billing).
        """
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint or "https://generativelanguage.googleapis.com/v1beta"
        self.project_id = project_id
        self._client: Optional[Any] = None

        logger.info(
            "Initialized GeminiClient",
            extra={
                "model": model,
                "endpoint": self.endpoint,
                "has_project_id": bool(project_id),
            },
        )

    def _get_client(self) -> Any:
        """Lazy-load the Gemini SDK client."""
        if self._client is None:
            try:
                import google.generativeai as genai  # type: ignore

                genai.configure(api_key=self.api_key)
                self._client = genai
                logger.debug("Gemini SDK configured successfully")
            except ImportError as e:
                logger.error(
                    "Failed to import google-generativeai. "
                    "Install with: pip install google-generativeai>=0.8.0"
                )
                raise ImportError(
                    "google-generativeai package required for Gemini support. "
                    "Install with: pip install google-generativeai>=0.8.0"
                ) from e
        return self._client

    def _convert_messages(
        self, messages: List[LlmMessage]
    ) -> tuple[Optional[str], List[Dict[str, Any]]]:
        """Convert messages to Gemini format.

        Gemini uses system instructions separate from the conversation history.

        Returns:
            Tuple of (system_instruction, conversation_messages)
        """
        system_instruction = None
        conversation_messages = []

        for msg in messages:
            if msg.role == "system":
                # Gemini has a separate system instruction field
                system_instruction = msg.content
            else:
                # Gemini uses "model" instead of "assistant"
                role = "model" if msg.role == "assistant" else "user"
                conversation_messages.append({"role": role, "parts": [msg.content]})

        return system_instruction, conversation_messages

    async def complete(self, request: LlmRequest) -> LlmResponse:
        """Generate a completion using Gemini API.

        Args:
            request: The LLM request with messages and parameters.

        Returns:
            LlmResponse with generated content and token usage.

        Raises:
            Exception: If the API request fails.
        """
        genai = self._get_client()

        try:
            # Convert messages to Gemini format
            system_instruction, conversation = self._convert_messages(request.messages)

            # Configure generation parameters
            generation_config: Dict[str, Any] = {}
            if request.temperature is not None:
                generation_config["temperature"] = request.temperature
            if request.max_tokens is not None:
                generation_config["max_output_tokens"] = request.max_tokens

            # Configure safety settings for technical/analytical content
            # Performance analysis queries are technical, not harmful
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_ONLY_HIGH",
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_ONLY_HIGH",
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_ONLY_HIGH",
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_ONLY_HIGH",
                },
            ]

            # Create model instance
            model_kwargs: Dict[str, Any] = {
                "model_name": self.model,
                "safety_settings": safety_settings,
            }
            if system_instruction:
                model_kwargs["system_instruction"] = system_instruction
            if generation_config:
                model_kwargs["generation_config"] = generation_config

            model = genai.GenerativeModel(**model_kwargs)

            logger.debug(
                "Sending request to Gemini",
                extra={
                    "model": self.model,
                    "message_count": len(request.messages),
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                },
            )

            # Generate content
            response = model.generate_content(conversation)

            # Extract content and usage
            # Handle safety filter blocking (finish_reason=2)
            try:
                content = response.text if hasattr(response, "text") else ""
            except ValueError as e:
                # Check if this is a safety filter block
                error_msg = str(e)
                if "finish_reason" in error_msg.lower():
                    # Extract finish reason from error or response
                    finish_reason = None
                    if hasattr(response, "candidates") and response.candidates:
                        candidate = response.candidates[0]
                        if hasattr(candidate, "finish_reason"):
                            finish_reason = candidate.finish_reason

                    logger.warning(
                        "Gemini response blocked by safety filters",
                        extra={
                            "finish_reason": finish_reason,
                            "error": error_msg,
                            "safety_ratings": (
                                getattr(response.candidates[0], "safety_ratings", None)
                                if hasattr(response, "candidates")
                                and response.candidates
                                else None
                            ),
                        },
                    )

                    # Return helpful error message instead of crashing
                    content = (
                        "I apologize, but I cannot complete this query due to "
                        "content safety restrictions. This can happen with very "
                        "long or complex queries. Please try:\n"
                        "1. Simplifying your query (fewer requirements/rules)\n"
                        "2. Breaking it into smaller queries\n"
                        "3. Rephrasing with less structured output requirements\n"
                        f"\nTechnical details: finish_reason={finish_reason}"
                    )
                else:
                    # Re-raise if not a safety filter issue
                    raise

            usage = None
            if hasattr(response, "usage_metadata"):
                metadata = response.usage_metadata
                usage = {
                    "prompt_tokens": getattr(metadata, "prompt_token_count", 0),
                    "completion_tokens": getattr(metadata, "candidates_token_count", 0),
                    "total_tokens": getattr(metadata, "total_token_count", 0),
                }

            logger.info(
                "Received response from Gemini",
                extra={
                    "content_length": len(content),
                    "usage": usage,
                },
            )

            return LlmResponse(content=content, usage=usage)

        except Exception as e:
            logger.error(
                "Gemini API request failed",
                extra={"error": str(e), "model": self.model},
                exc_info=True,
            )
            raise

    async def complete_stream(
        self, request: LlmRequest, callback: StreamCallback
    ) -> None:
        """Generate a streaming completion using Gemini API.

        Args:
            request: The LLM request with messages and parameters.
            callback: Function called with each content chunk.

        Raises:
            Exception: If the streaming request fails.
        """
        genai = self._get_client()

        try:
            # Convert messages to Gemini format
            system_instruction, conversation = self._convert_messages(request.messages)

            # Configure generation parameters
            generation_config: Dict[str, Any] = {}
            if request.temperature is not None:
                generation_config["temperature"] = request.temperature
            if request.max_tokens is not None:
                generation_config["max_output_tokens"] = request.max_tokens

            # Create model instance
            model_kwargs: Dict[str, Any] = {"model_name": self.model}
            if system_instruction:
                model_kwargs["system_instruction"] = system_instruction
            if generation_config:
                model_kwargs["generation_config"] = generation_config

            model = genai.GenerativeModel(**model_kwargs)

            logger.debug(
                "Starting streaming request to Gemini",
                extra={"model": self.model, "message_count": len(request.messages)},
            )

            # Stream content
            response = model.generate_content(conversation, stream=True)

            for chunk in response:
                if hasattr(chunk, "text") and chunk.text:
                    callback(chunk.text)

            logger.info(
                "Streaming response complete",
                extra={"model": self.model},
            )

        except Exception as e:
            logger.error(
                "Gemini streaming request failed",
                extra={"error": str(e), "model": self.model},
                exc_info=True,
            )
            raise


def create_llm_client(env: Any) -> Optional[LlmClient]:
    """Create an LLM client based on environment configuration.

    Args:
        env: Environment settings object with LLM configuration.

    Returns:
        LlmClient instance, or None if LLM is not configured.

    Raises:
        ValueError: If provider is specified but configuration is invalid.
    """
    # Check if LLM is configured
    llm_provider = getattr(env, "LLM_PROVIDER", None)
    llm_api_key = getattr(env, "LLM_API_KEY", None)
    llm_model = getattr(env, "LLM_MODEL", None)

    if not llm_provider:
        logger.info("LLM provider not configured, LLM features disabled")
        return None

    if not llm_api_key:
        logger.warning(
            "LLM_PROVIDER set but LLM_API_KEY missing, LLM features disabled"
        )
        return None

    if not llm_model:
        logger.warning("LLM_PROVIDER set but LLM_MODEL missing, LLM features disabled")
        return None

    logger.info(
        "Initializing LLM client",
        extra={"provider": llm_provider, "model": llm_model},
    )

    # Create provider-specific client
    if llm_provider.lower() == "gemini":
        endpoint = getattr(env, "LLM_GEMINI_ENDPOINT", None)
        project_id = getattr(env, "LLM_GEMINI_PROJECT", None)
        return GeminiClient(
            api_key=llm_api_key,
            model=llm_model,
            endpoint=endpoint,
            project_id=project_id,
        )
    else:
        logger.error(
            f"Unsupported LLM provider: {llm_provider}. " "Supported providers: gemini"
        )
        raise ValueError(
            f"Unsupported LLM provider: {llm_provider}. " "Currently supported: gemini"
        )
