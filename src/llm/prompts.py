"""System prompts for LLM-powered natural language query processing.

These prompts define the LLM's role and tool call format for orchestration.
Domain knowledge is NOT duplicated here - it lives in MCP Resources and tool
descriptions, following our PRIMARY MISSION of single-source-of-truth domain
encoding.

The LLM is a Domain MCP client, just like Claude/Cursor, and should rely on
the same domain knowledge encoding (MCP Resources, tool descriptions,
normalization layer) that all AI clients use.

NOTE: Tool schemas are dynamically extracted from actual MCP tool
definitions in tool_schemas.py. This ensures /api/query and direct MCP access
always see the same tool interface without manual synchronization.
"""


def create_user_prompt(query: str) -> str:
    """Create a formatted user prompt for a natural language query.

    Args:
        query: The user's natural language query.

    Returns:
        Formatted prompt with query and execution instructions.
    """
    return f"""User Query: {query}

IMPORTANT: You must EXECUTE the necessary tool calls using the TOOL_CALL: format \
specified in the system prompt.

DO NOT just explain what you would do. ACTUALLY call the tools by outputting:
TOOL_CALL: {{"name": "tool_name", "arguments": {{...}}}}

Think step-by-step:
1. Determine which tool(s) to call and what parameters to use
2. Output the TOOL_CALL: line(s) for each tool
3. Wait for results
4. Provide your final answer based on the actual data

Start by making your first tool call now."""
