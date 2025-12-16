"""LLM integration for natural language query processing.

This module provides LLM-powered natural language query capabilities for the
Domain MCP server. It enables users to send natural language questions to the
/api/query HTTP endpoint and receive formatted answers based on domain data.

Architecture:
- client.py: Multi-provider LLM client (Gemini primary, OpenAI/Anthropic future)
- orchestrator.py: Query orchestration, tool call parsing, conversation management
- prompts.py: Domain-specific system prompts encoding RHIVOS/AutoSD knowledge

Example usage:
    from src.llm.client import create_llm_client
    from src.llm.orchestrator import QueryOrchestrator
    from src.config.models import EnvSettings

    env = EnvSettings()
    llm_client = create_llm_client(env)
    orchestrator = QueryOrchestrator(llm_client, mcp_server)
    result = await orchestrator.execute_query("Show RHEL boot times for last week")
"""

from .client import (
    GeminiClient,
    LlmClient,
    LlmMessage,
    LlmRequest,
    LlmResponse,
    StreamCallback,
    create_llm_client,
)
from .orchestrator import (
    OrchestrationResult,
    QueryOrchestrator,
    ToolCall,
    ToolResult,
    create_orchestrator,
)
from .prompts import (
    create_user_prompt,
)
from .tool_schemas import (
    create_system_prompt_with_tools,
    get_tool_schemas_for_llm,
)

__all__ = [
    # Client
    "GeminiClient",
    "LlmClient",
    "LlmMessage",
    "LlmRequest",
    "LlmResponse",
    "StreamCallback",
    "create_llm_client",
    # Orchestrator
    "OrchestrationResult",
    "QueryOrchestrator",
    "ToolCall",
    "ToolResult",
    "create_orchestrator",
    # Prompts
    "create_user_prompt",
    # Tool Schemas (dynamic extraction)
    "create_system_prompt_with_tools",
    "get_tool_schemas_for_llm",
]
