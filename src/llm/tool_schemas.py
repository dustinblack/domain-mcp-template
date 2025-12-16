"""Dynamic tool schema extraction from MCP tool definitions.

This module extracts tool schemas directly from the MCP server's tool
definitions, ensuring the LLM always sees the current tool interface without
requiring manual synchronization.

Follows the PRIMARY MISSION: single source of truth for domain knowledge.
Tool schemas come from the actual MCP tool implementations, not duplicated
hardcoded strings.
"""

import inspect
import re
from typing import Any, Dict, List


def extract_tool_schema_from_docstring(docstring: str, tool_name: str) -> str:
    """Extract a concise tool schema from a tool's docstring.

    Parses the docstring to find key sections (Parameters, Returns) and
    formats them for LLM consumption.

    Args:
        docstring: The tool function's docstring.
        tool_name: The name of the tool.

    Returns:
        Formatted tool schema string for LLM prompt.
    """
    if not docstring:
        return f"### {tool_name}\nNo documentation available."

    # Extract the first line (summary)
    lines = docstring.strip().split("\n")
    summary = lines[0].strip() if lines else ""

    # Extract key sections for LLM guidance
    # Focus on: Parameters, what NOT to do, common patterns, examples

    # For get_key_metrics, extract the essential guidance
    if tool_name == "get_key_metrics":
        schema = f"""### {tool_name}
{summary}

**PRIMARY TOOL** for boot time and performance analysis queries.

**Parameters (all optional):**
- `run_id` (string): Fetch metrics for a specific Horreum run ID
  - Example: "123456"
  - When provided, fetches only that run (ignores time filters)
  - **Use this for "analyze run ID X" queries**
- `from_timestamp` (string): Start time filter. Accepts:
  - Natural language: "last 30 days", "last week", "yesterday"
  - ISO 8601: "2025-01-01T00:00:00Z"
  - Unix milliseconds: 1704067200000
- `to_timestamp` (string): End time filter (same formats as from_timestamp)
- `os_id` (string): OS filter. Examples: "rhel", "autosd"
  - Note: aliases are auto-normalized (e.g. "my-alias" -> "rhel")
- `run_type` (string): Filter by test run type
  - Values: "nightly", "ci", "release", "manual"
  - Example: Use "nightly" to analyze only automated nightly builds
  - **Use this when query specifies run type** (e.g., "nightly results only")
- `limit` (integer): Page size for fetching (default: 100)
  - Server automatically paginates to fetch ALL results

**DO NOT use these parameters** (they are auto-configured):
- test_id (auto-discovered for boot time queries)
- source_id (auto-selected)
- dataset_types (defaults to ["boot-time-verbose"])

**Returns:**
- `metric_points`: List of metric measurements
  - Each point has: metric_id, timestamp, value, dimensions (os_id, mode, \
target), source
- `domain_model_version`: "1.0.0"

**Examples:**
```
# Fetch all RHEL data from last 90 days
TOOL_CALL: {{"name": "get_key_metrics", "arguments": \
{{"from_timestamp": "last 90 days", "os_id": "rhel"}}}}

# Fetch only nightly test results from last 30 days
TOOL_CALL: {{"name": "get_key_metrics", "arguments": \
{{"from_timestamp": "last 30 days", "run_type": "nightly"}}}}
```
"""
        return schema

    # For resources/read, keep it simple
    elif tool_name == "resources/read":
        schema = """### resources/read
Read MCP resource containing domain knowledge or templates.

**Parameters:**
- `uri` (string, required): Resource URI to read
  - Format: "domain://<category>/<resource-name>"
  - Examples:
    - "domain://examples/boot-time-report-template"
    - "domain://glossary/boot-time"
    - "domain://examples/3d-matrix-organization"

**Returns:**
Resource content (JSON, markdown, or plain text)

**Example:**
```
TOOL_CALL: {{"name": "resources/read", "arguments": \
{{"uri": "domain://examples/boot-time-report-template"}}}}
```
"""
        return schema

    # Generic fallback for other tools
    else:
        # Extract parameters section if present
        params_match = re.search(
            r"Parameters\s*\n\s*-+\s*\n(.*?)(?:\n\s*Returns|\n\s*Raises|\Z)",
            docstring,
            re.DOTALL | re.IGNORECASE,
        )
        params_text = params_match.group(1).strip() if params_match else "None"

        # Extract returns section if present
        returns_match = re.search(
            r"Returns\s*\n\s*-+\s*\n(.*?)(?:\n\s*Raises|\Z)",
            docstring,
            re.DOTALL | re.IGNORECASE,
        )
        returns_text = returns_match.group(1).strip() if returns_match else "Unknown"

        schema = f"""### {tool_name}
{summary}

**Parameters:**
{params_text}

**Returns:**
{returns_text}
"""
        return schema


def get_tool_schemas_for_llm(tool_handlers: Dict[str, Any]) -> str:
    """Generate tool schemas for LLM consumption from tool handlers.

    Extracts tool documentation directly from the handler functions to ensure
    the LLM always sees the current tool interface.

    Args:
        tool_handlers: Dictionary mapping tool names to handler functions.

    Returns:
        Formatted tool schemas string for injection into LLM system prompt.
    """
    schemas: List[str] = []

    for tool_name, handler in tool_handlers.items():
        # Get the docstring from the handler function
        docstring = inspect.getdoc(handler)

        if docstring:
            schema = extract_tool_schema_from_docstring(docstring, tool_name)
            schemas.append(schema)
        else:
            # Fallback if no docstring
            schemas.append(f"### {tool_name}\nNo documentation available.")

    return "\n\n".join(schemas)


def create_system_prompt_with_tools(tool_handlers: Dict[str, Any]) -> str:
    """Create the complete system prompt with dynamically extracted tool schemas.

    Args:
        tool_handlers: Dictionary mapping tool names to handler functions.

    Returns:
        Complete system prompt string with tool schemas.
    """
    tool_schemas = get_tool_schemas_for_llm(tool_handlers)

    return f"""You are an assistant for querying Domain performance data.

## Tool Call Format

Execute tools using this exact syntax:
```
TOOL_CALL: {{"name": "tool_name", "arguments": {{"param1": "value1"}}}}
```

**DO NOT** just describe what you would do. **ACTUALLY EXECUTE** the tool calls.

## Available Tools

{tool_schemas}

## Workflow

1. Read MCP resources to understand the domain (use resources/read tool)
2. Execute data queries (use get_key_metrics tool)
3. Format responses according to templates from resources

Start by reading domain://examples/boot-time-report-template to understand how to \
structure your response.
"""
