"""Unit tests for query orchestrator (Phase 6.2).

Tests QueryOrchestrator implementation including:
- Tool call parsing (TOOL_CALL format, JSON blocks)
- Iteration logic (multi-turn conversations)
- Tool execution (mocked tool handlers)
- Error handling (tool failures, LLM errors, timeouts)
- Metadata tracking (durations, call counts)
"""

import json
from unittest.mock import AsyncMock, Mock

import pytest

from src.llm.client import LlmResponse
from src.llm.orchestrator import (
    OrchestrationResult,
    QueryOrchestrator,
    ToolCall,
    ToolResult,
    create_orchestrator,
)


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = Mock()
    client.complete = AsyncMock()
    return client


@pytest.fixture
def mock_tool_handlers():
    """Create mock tool handlers."""
    return {
        "get_key_metrics": AsyncMock(
            return_value={
                "metric_points": [{"metric_id": "boot.time.total", "value": 1500}],
                "domain_model_version": "1.0.0",
            }
        ),
        "resources/read": AsyncMock(
            return_value={
                "contents": [
                    {
                        "uri": "domain://examples/test",
                        "mimeType": "application/json",
                        "text": json.dumps({"example": "data"}),
                    }
                ]
            }
        ),
    }


@pytest.fixture
def orchestrator(mock_llm_client, mock_tool_handlers):
    """Create QueryOrchestrator instance."""
    return QueryOrchestrator(
        llm_client=mock_llm_client,
        tool_handlers=mock_tool_handlers,
        max_iterations=5,
        temperature=0.1,
    )


class TestQueryOrchestrator:
    """Test QueryOrchestrator functionality."""

    def test_initialization(self, mock_llm_client, mock_tool_handlers):
        """Test orchestrator initialization."""
        orch = QueryOrchestrator(
            llm_client=mock_llm_client,
            tool_handlers=mock_tool_handlers,
            max_iterations=10,
            temperature=0.2,
        )
        assert orch.llm_client == mock_llm_client
        assert orch.tool_handlers == mock_tool_handlers
        assert orch.max_iterations == 10
        assert orch.temperature == 0.2
        # System prompt is added on init
        assert len(orch.conversation_history) == 1
        assert orch.conversation_history[0].role == "system"

    def test_parse_tool_calls_basic_format(self, orchestrator):
        """Test parsing TOOL_CALL: {...} format."""
        content = """Let me fetch that data for you.

TOOL_CALL: {"name": "get_key_metrics", "arguments": {"os_id": "rhel"}}

I'll use this to get the data."""

        tool_calls = orchestrator._parse_tool_calls(content)

        assert len(tool_calls) == 1
        assert tool_calls[0].name == "get_key_metrics"
        assert tool_calls[0].arguments == {"os_id": "rhel"}

    def test_parse_tool_calls_multiple(self, orchestrator):
        """Test parsing multiple tool calls."""
        content = """First, I'll read the template:

TOOL_CALL: {"name": "resources/read", "arguments": \
{"uri": "domain://examples/template"}}

Then I'll get the metrics:

TOOL_CALL: {"name": "get_key_metrics", "arguments": \
{"from_timestamp": "last week"}}
"""

        tool_calls = orchestrator._parse_tool_calls(content)

        assert len(tool_calls) == 2
        assert tool_calls[0].name == "resources/read"
        assert tool_calls[1].name == "get_key_metrics"

    def test_parse_tool_calls_json_block(self, orchestrator):
        """Test parsing ```json block format."""
        content = """Here's the tool call:

```json
{"name": "get_key_metrics", "arguments": \
{"os_id": "autosd", "from_timestamp": "yesterday"}}
```

This will fetch the data."""

        tool_calls = orchestrator._parse_tool_calls(content)

        assert len(tool_calls) == 1
        assert tool_calls[0].name == "get_key_metrics"
        assert tool_calls[0].arguments["os_id"] == "autosd"

    def test_parse_tool_calls_no_calls(self, orchestrator):
        """Test parsing content with no tool calls."""
        content = "This is just a regular response with no tool calls."

        tool_calls = orchestrator._parse_tool_calls(content)

        assert len(tool_calls) == 0

    def test_parse_tool_calls_invalid_json(self, orchestrator):
        """Test parsing with invalid JSON (should skip)."""
        content = """TOOL_CALL: {invalid json here}

TOOL_CALL: {"name": "valid_call", "arguments": {}}"""

        tool_calls = orchestrator._parse_tool_calls(content)

        # Should only get the valid one
        assert len(tool_calls) == 1
        assert tool_calls[0].name == "valid_call"

    @pytest.mark.asyncio
    async def test_execute_tool_success(self, orchestrator):
        """Test successful tool execution."""
        tool_call = ToolCall(
            name="get_key_metrics",
            arguments={"os_id": "rhel", "from_timestamp": "last week"},
        )

        result = await orchestrator._execute_tool(tool_call)

        # Handler returns dict directly
        assert isinstance(result, dict)
        assert "domain_model_version" in result
        assert result["domain_model_version"] == "1.0.0"
        orchestrator.tool_handlers["get_key_metrics"].assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_unknown(self, orchestrator):
        """Test execution of unknown tool."""
        tool_call = ToolCall(name="unknown_tool", arguments={})

        # Unknown tool raises ValueError
        with pytest.raises(ValueError, match="Tool 'unknown_tool' not found"):
            await orchestrator._execute_tool(tool_call)

    @pytest.mark.asyncio
    async def test_execute_tool_handler_error(self, orchestrator):
        """Test handling of tool execution errors."""
        orchestrator.tool_handlers["get_key_metrics"].side_effect = Exception(
            "Database connection failed"
        )

        tool_call = ToolCall(name="get_key_metrics", arguments={})

        # Tool execution errors propagate up
        with pytest.raises(Exception, match="Database connection failed"):
            await orchestrator._execute_tool(tool_call)

    def test_format_tool_results(self, orchestrator):
        """Test formatting of tool results for LLM."""
        tool_results = [
            ToolResult(
                tool="get_key_metrics",
                success=True,
                result={"metric_points": []},
            )
        ]

        formatted = orchestrator._format_tool_results(tool_results)

        assert "TOOL_RESULT" in formatted
        assert "get_key_metrics" in formatted
        assert "metric_points" in formatted

    @pytest.mark.asyncio
    async def test_execute_query_simple(self, orchestrator, mock_llm_client):
        """Test simple query execution with one tool call."""
        # Mock LLM responses
        mock_llm_client.complete.side_effect = [
            # First call: LLM decides to call tool
            LlmResponse(
                content='TOOL_CALL: {"name": "get_key_metrics", '
                '"arguments": {"os_id": "rhel"}}',
                usage={
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            ),
            # Second call: LLM provides final answer
            LlmResponse(
                content="The RHEL boot time is 1500ms.",
                usage={
                    "prompt_tokens": 200,
                    "completion_tokens": 20,
                    "total_tokens": 220,
                },
            ),
        ]

        result = await orchestrator.execute_query("Show RHEL boot times")

        assert isinstance(result, OrchestrationResult)
        assert result.answer == "The RHEL boot time is 1500ms."
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["tool"] == "get_key_metrics"
        assert result.llm_calls == 2
        assert result.total_duration_ms >= 0  # Can be 0 with mocked time

    @pytest.mark.asyncio
    async def test_execute_query_no_tool_calls(self, orchestrator, mock_llm_client):
        """Test query where LLM responds directly without tools."""
        mock_llm_client.complete.return_value = LlmResponse(
            content="I cannot answer that question without more information.",
            usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        )

        result = await orchestrator.execute_query("What is the meaning of life?")

        assert "cannot answer" in result.answer.lower()
        assert len(result.tool_calls) == 0
        assert result.llm_calls == 1

    @pytest.mark.asyncio
    async def test_execute_query_max_iterations(self, orchestrator, mock_llm_client):
        """Test max iterations handling."""
        # Mock LLM to keep calling tools indefinitely
        mock_llm_client.complete.return_value = LlmResponse(
            content='TOOL_CALL: {"name": "get_key_metrics", "arguments": {}}',
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )

        result = await orchestrator.execute_query("Test query")

        assert "maximum number of iterations" in result.answer
        assert result.llm_calls == orchestrator.max_iterations

    @pytest.mark.asyncio
    async def test_execute_query_tool_error_handling(
        self, orchestrator, mock_llm_client
    ):
        """Test handling of tool execution errors."""
        # First call: tool call
        # Second call: final answer after seeing error
        mock_llm_client.complete.side_effect = [
            LlmResponse(
                content='TOOL_CALL: {"name": "get_key_metrics", "arguments": {}}',
                usage={
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            ),
            LlmResponse(
                content="I encountered an error fetching the data.",
                usage={
                    "prompt_tokens": 200,
                    "completion_tokens": 20,
                    "total_tokens": 220,
                },
            ),
        ]

        # Make tool fail
        orchestrator.tool_handlers["get_key_metrics"].side_effect = Exception(
            "Tool failed"
        )

        result = await orchestrator.execute_query("Get metrics")

        assert len(result.tool_calls) == 1
        assert "error" in result.tool_calls[0]["result"]
        assert "error" in result.answer.lower()

    @pytest.mark.asyncio
    async def test_execute_query_conversation_history(
        self, orchestrator, mock_llm_client
    ):
        """Test that conversation history is maintained."""
        mock_llm_client.complete.return_value = LlmResponse(
            content="Response",
            usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        )

        await orchestrator.execute_query("First query")

        # History should have system, user, and assistant messages
        assert len(orchestrator.conversation_history) == 3
        assert orchestrator.conversation_history[0].role == "system"
        assert orchestrator.conversation_history[1].role == "user"
        assert orchestrator.conversation_history[2].role == "assistant"


class TestCreateOrchestrator:
    """Test create_orchestrator factory function."""

    def test_create_orchestrator(self, mock_llm_client, mock_tool_handlers):
        """Test factory creates orchestrator successfully."""
        orch = create_orchestrator(
            llm_client=mock_llm_client,
            tool_handlers=mock_tool_handlers,
            max_iterations=10,
            temperature=0.2,
        )

        assert isinstance(orch, QueryOrchestrator)
        assert orch.max_iterations == 10
        assert orch.temperature == 0.2

    def test_create_orchestrator_defaults(self, mock_llm_client, mock_tool_handlers):
        """Test factory uses default values."""
        orch = create_orchestrator(
            llm_client=mock_llm_client, tool_handlers=mock_tool_handlers
        )

        assert orch.max_iterations == 10
        assert orch.temperature == 0.1
