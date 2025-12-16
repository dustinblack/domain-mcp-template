"""Query orchestration system for LLM-powered natural language queries.

This module coordinates between the LLM and Domain MCP tools, enabling multi-step
query execution where the LLM can call tools, analyze results, and make additional
tool calls as needed.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .client import LlmClient, LlmMessage, LlmRequest
from .prompts import create_user_prompt
from .tool_schemas import create_system_prompt_with_tools

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """Tool call request parsed from LLM response."""

    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolResult:
    """Result of a tool execution."""

    tool: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class OrchestrationResult:
    """Orchestration result containing the final answer and execution trace."""

    answer: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    total_duration_ms: int = 0
    llm_calls: int = 0
    total_tokens: int = 0  # Total tokens used (prompt + completion)


class QueryOrchestrator:
    """Orchestrator for natural language queries using LLM + MCP tools.

    Manages conversation history, parses tool calls from LLM responses,
    executes Domain MCP tools, and iterates until a final answer is reached.

    Example:
        orchestrator = QueryOrchestrator(llm_client, mcp_server)
        result = await orchestrator.execute_query(
            "Show RHEL boot times for last week"
        )
        print(result.answer)
    """

    def __init__(
        self,
        llm_client: LlmClient,
        tool_handlers: Dict[str, Any],
        max_iterations: int = 10,
        temperature: float = 0.1,
    ):
        """Initialize query orchestrator.

        Args:
            llm_client: LLM client for generating responses.
            tool_handlers: Dictionary mapping tool names to handler functions.
            max_iterations: Maximum LLM iterations before timeout (default: 10).
            temperature: LLM temperature for response generation (default: 0.1).
        """
        self.llm_client = llm_client
        self.tool_handlers = tool_handlers
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.conversation_history: List[LlmMessage] = []

        # Initialize with system prompt (includes dynamic tool schemas)
        system_prompt = create_system_prompt_with_tools(tool_handlers)
        self.conversation_history.append(
            LlmMessage(role="system", content=system_prompt)
        )

        logger.info(
            "QueryOrchestrator initialized",
            extra={
                "max_iterations": max_iterations,
                "temperature": temperature,
                "available_tools": list(tool_handlers.keys()),
            },
        )

    async def execute_query(self, query: str) -> OrchestrationResult:
        """Execute a natural language query.

        Args:
            query: The user's natural language query.

        Returns:
            OrchestrationResult with answer and execution trace.
        """
        start_time = time.time()
        tool_calls_trace: List[Dict[str, Any]] = []
        llm_calls = 0

        try:
            # Add user query to conversation
            user_prompt = create_user_prompt(query)
            self.conversation_history.append(
                LlmMessage(role="user", content=user_prompt)
            )

            logger.info(
                "Starting query execution",
                extra={
                    "query": query,
                    "conversation_length": len(self.conversation_history),
                },
            )

            iterations = 0
            total_tokens = 0  # Track cumulative token usage (Phase 6.3)
            final_answer: Optional[str] = None

            while iterations < self.max_iterations and final_answer is None:
                iterations += 1
                llm_calls += 1

                logger.debug(
                    "LLM iteration",
                    extra={
                        "iteration": iterations,
                        "history_length": len(self.conversation_history),
                    },
                )

                # Call LLM
                llm_start = time.time()
                response = await self.llm_client.complete(
                    LlmRequest(
                        messages=self.conversation_history,
                        temperature=self.temperature,
                        max_tokens=4096,
                    )
                )
                llm_duration = int((time.time() - llm_start) * 1000)

                # Track token usage (Phase 6.3)
                if response.usage:
                    tokens_this_call = response.usage.get("total_tokens", 0)
                    total_tokens += tokens_this_call

                content = response.content.strip()
                logger.debug(
                    "LLM response received",
                    extra={
                        "iteration": iterations,
                        "content_length": len(content),
                        "duration_ms": llm_duration,
                        "usage": response.usage,
                        "total_tokens": total_tokens,
                    },
                )

                # Add assistant response to history
                self.conversation_history.append(
                    LlmMessage(role="assistant", content=content)
                )

                # Parse response for tool calls
                tool_call_requests = self._parse_tool_calls(content)

                if not tool_call_requests:
                    # No more tool calls - this is the final answer
                    final_answer = content
                    logger.info(
                        "Final answer received",
                        extra={"iteration": iterations, "answer_length": len(content)},
                    )
                    break

                logger.info(
                    "Tool calls requested",
                    extra={
                        "iteration": iterations,
                        "tool_count": len(tool_call_requests),
                        "tools": [tc.name for tc in tool_call_requests],
                    },
                )

                # Execute tool calls
                results: List[ToolResult] = []
                for tool_call in tool_call_requests:
                    tool_start = time.time()
                    try:
                        logger.debug(
                            "Executing tool",
                            extra={
                                "tool": tool_call.name,
                                "arguments": tool_call.arguments,
                            },
                        )

                        result = await self._execute_tool(tool_call)
                        tool_duration = int((time.time() - tool_start) * 1000)

                        results.append(
                            ToolResult(
                                tool=tool_call.name,
                                success=True,
                                result=result,
                            )
                        )

                        tool_calls_trace.append(
                            {
                                "tool": tool_call.name,
                                "arguments": tool_call.arguments,
                                "result": result,
                                "duration_ms": tool_duration,
                            }
                        )

                        logger.info(
                            "Tool executed successfully",
                            extra={
                                "tool": tool_call.name,
                                "duration_ms": tool_duration,
                            },
                        )

                    except Exception as e:
                        tool_duration = int((time.time() - tool_start) * 1000)
                        error_msg = str(e)

                        results.append(
                            ToolResult(
                                tool=tool_call.name,
                                success=False,
                                error=error_msg,
                            )
                        )

                        tool_calls_trace.append(
                            {
                                "tool": tool_call.name,
                                "arguments": tool_call.arguments,
                                "result": {"error": error_msg},
                                "duration_ms": tool_duration,
                            }
                        )

                        logger.error(
                            "Tool execution failed",
                            extra={
                                "tool": tool_call.name,
                                "error": error_msg,
                                "duration_ms": tool_duration,
                            },
                        )

                # Add tool results to conversation
                results_message = self._format_tool_results(results)
                self.conversation_history.append(
                    LlmMessage(role="user", content=results_message)
                )

                # If all tools failed, stop iteration
                if results and all(not r.success for r in results):
                    final_answer = (
                        "I encountered errors while trying to query the data:\n\n"
                        + "\n".join(f"- {r.tool}: {r.error}" for r in results)
                        + "\n\nPlease check the query parameters or try a different "
                        "query."
                    )
                    logger.warning(
                        "All tools failed, terminating iteration",
                        extra={"iteration": iterations},
                    )
                    break

            # Handle max iterations reached
            if final_answer is None:
                final_answer = (
                    f"I reached the maximum number of iterations "
                    f"({self.max_iterations}) "
                    "without completing the query. Please try a simpler or more "
                    "specific query."
                )
                logger.warning(
                    "Max iterations reached without final answer",
                    extra={"iterations": iterations},
                )

            total_duration = int((time.time() - start_time) * 1000)

            logger.info(
                "Query execution complete",
                extra={
                    "total_duration_ms": total_duration,
                    "llm_calls": llm_calls,
                    "tool_calls": len(tool_calls_trace),
                    "iterations": iterations,
                    "total_tokens": total_tokens,
                },
            )

            return OrchestrationResult(
                answer=final_answer,
                tool_calls=tool_calls_trace,
                total_duration_ms=total_duration,
                llm_calls=llm_calls,
                total_tokens=total_tokens,
            )

        except Exception as e:
            logger.error(
                "Query orchestration failed",
                extra={"query": query, "error": str(e)},
                exc_info=True,
            )
            raise

    def _parse_tool_calls(self, content: str) -> List[ToolCall]:
        """Parse tool call requests from LLM response.

        Looks for JSON-formatted tool calls in the response.
        Expected formats:
        1. TOOL_CALL: {"name": "tool_name", "arguments": {...}}
        2. ```json\n{"tool": "name", "parameters": {...}}\n```

        Args:
            content: The LLM response content.

        Returns:
            List of parsed tool calls.
        """
        tool_calls: List[ToolCall] = []

        # Pattern 1: TOOL_CALL: format
        # Use a state machine approach to handle multiline nested JSON
        tool_call_starts = []
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "TOOL_CALL:" in line:
                # Find the position after TOOL_CALL:
                idx = line.find("TOOL_CALL:")
                start_pos = sum(len(prev_line) + 1 for prev_line in lines[:i])
                start_pos += idx + len("TOOL_CALL:")
                tool_call_starts.append(start_pos)

        for start_pos in tool_call_starts:
            # Find the matching JSON object starting from this position
            json_str = self._extract_json_object(content[start_pos:])
            if json_str:
                try:
                    parsed = json.loads(json_str)
                    name = parsed.get("name")
                    arguments = parsed.get("arguments", {})

                    if name:
                        tool_calls.append(ToolCall(name=name, arguments=arguments))
                        logger.debug(
                            "Parsed TOOL_CALL format",
                            extra={"tool": name, "arguments": arguments},
                        )
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Failed to parse TOOL_CALL JSON",
                        extra={"raw": json_str[:200], "error": str(e)},
                    )

        # Pattern 2: JSON code blocks
        json_block_pattern = r"```json\s*\n({[\s\S]*?})\s*\n```"
        for match in re.finditer(json_block_pattern, content):
            json_str = match.group(1)
            try:
                parsed = json.loads(json_str)
                name = parsed.get("tool") or parsed.get("name")
                arguments = parsed.get("parameters") or parsed.get("arguments", {})

                if name:
                    tool_calls.append(ToolCall(name=name, arguments=arguments))
                    logger.debug(
                        "Parsed JSON block format",
                        extra={"tool": name, "arguments": arguments},
                    )
            except json.JSONDecodeError as e:
                logger.warning(
                    "Failed to parse JSON block",
                    extra={"raw": json_str[:100], "error": str(e)},
                )

        return tool_calls

    async def _execute_tool(self, tool_call: ToolCall) -> Any:
        """Execute a tool call using the registered handler.

        Args:
            tool_call: The tool call to execute.

        Returns:
            The tool execution result.

        Raises:
            ValueError: If tool is not found.
            Exception: If tool execution fails.
        """
        tool_name = tool_call.name
        arguments = tool_call.arguments

        # Look up tool handler
        handler = self.tool_handlers.get(tool_name)
        if not handler:
            logger.error("Tool not found", extra={"tool": tool_name})
            raise ValueError(f"Tool '{tool_name}' not found")

        # Execute tool handler
        logger.debug(
            "Calling tool handler", extra={"tool": tool_name, "arguments": arguments}
        )

        result = await handler(**arguments)
        return result

    def _extract_json_object(self, text: str) -> Optional[str]:
        """Extract a complete JSON object from text using brace counting.

        Handles multiline JSON with arbitrary nesting levels.

        Args:
            text: The text to extract JSON from (should start near a '{').

        Returns:
            The extracted JSON string, or None if no valid object found.
        """
        # Find the first opening brace
        start_idx = text.find("{")
        if start_idx == -1:
            return None

        # Count braces to find the matching closing brace
        brace_count = 0
        in_string = False
        escape_next = False

        for i in range(start_idx, len(text)):
            char = text[i]

            if escape_next:
                escape_next = False
                continue

            if char == "\\":
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if not in_string:
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        # Found the matching closing brace
                        return text[start_idx : i + 1]

        return None

    def _format_tool_results(self, results: List[ToolResult]) -> str:
        """Format tool results for the LLM.

        Args:
            results: The tool execution results.

        Returns:
            Formatted message for the LLM.
        """
        parts = []
        for result in results:
            if result.success:
                # Format result as JSON for structured data
                try:
                    result_str = json.dumps(result.result, indent=2)
                except (TypeError, ValueError):
                    result_str = str(result.result)

                parts.append(f"TOOL_RESULT [{result.tool}]:\n{result_str}")
            else:
                parts.append(f"TOOL_ERROR [{result.tool}]: {result.error}")

        formatted = "\n\n".join(parts)
        return (
            f"Tool execution results:\n\n{formatted}\n\n"
            "Based on these results, please provide your analysis or make additional "
            "tool calls if needed."
        )

    def reset(self) -> None:
        """Reset the conversation history."""
        system_prompt = create_system_prompt_with_tools(self.tool_handlers)
        self.conversation_history = [LlmMessage(role="system", content=system_prompt)]
        logger.debug("Conversation history reset")


def create_orchestrator(
    llm_client: LlmClient,
    tool_handlers: Dict[str, Any],
    max_iterations: int = 10,
    temperature: float = 0.1,
) -> QueryOrchestrator:
    """Create a query orchestrator instance.

    Args:
        llm_client: The LLM client to use.
        tool_handlers: Dictionary mapping tool names to handler functions.
        max_iterations: Maximum number of LLM iterations (default: 10).
        temperature: LLM temperature setting (default: 0.1 for deterministic responses).

    Returns:
        A new QueryOrchestrator instance.
    """
    return QueryOrchestrator(llm_client, tool_handlers, max_iterations, temperature)
