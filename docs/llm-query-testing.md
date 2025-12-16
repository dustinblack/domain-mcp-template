# Functional Testing Guide: LLM Query Endpoint

This guide explains how to functionally test the `/api/query` endpoint with the
Gemini LLM integration (Phase 6.1).

## Prerequisites

### 1. Install Dependencies

```bash
pip install google-generativeai>=0.8.0
```

### 2. Get a Gemini API Key

**Option A: Public Gemini API (Recommended for testing)**
1. Go to https://aistudio.google.com/app/apikey
2. Click "Get API key" or "Create API key"
3. Copy your API key

**Option B: Corporate/Vertex AI**
1. Set up Google Cloud project with Vertex AI enabled
2. Get credentials and endpoint URL
3. Use corporate configuration (see below)

### 3. Configure Environment Variables

Create a `.env` file or export variables:

```bash
# Required
export LLM_PROVIDER=gemini
export LLM_API_KEY=your-api-key-here
export LLM_MODEL=gemini-1.5-flash  # or gemini-1.5-pro

# Optional (for corporate/Vertex AI)
export LLM_GEMINI_ENDPOINT=https://your-endpoint.googleapis.com
export LLM_GEMINI_PROJECT=your-project-id

# Optional tuning
export LLM_TEMPERATURE=0.1  # default: 0.1 (deterministic)
export LLM_MAX_TOKENS=4096  # default: 4096

# Server configuration (if needed)
export DOMAIN_MCP_HTTP_TOKEN=your-test-token  # for auth
```

## Start the Server

### HTTP Mode

```bash
cd /path/to/your-domain-mcp
python3 -m src.server.cli --http --port 8000
```

The server will log:
```
INFO     src.server.http:http.py:1617 /api/query endpoint enabled
         extra={'llm_provider': 'gemini', 'llm_model': 'gemini-1.5-flash'}
```

If you see this instead, LLM is not configured:
```
INFO     src.server.http:http.py:1589 /api/query endpoint disabled: LLM not configured
```

## Test with curl

### Basic Query (No Auth)

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Show metrics for [your domain] over the last week"}'
# Example (PerfScale): "Show RHEL boot times for the last week"
```

### With Authentication

```bash
export TOKEN=your-test-token

curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "Show metrics for [your domain] over the last week"}'
```

### Expected Response Format

```json
{
  "query": "Show metrics for [your domain] over the last week",
  "answer": "Based on the data...",
  "metadata": {
    "tool_calls": 2,
    "llm_calls": 3,
    "duration_ms": 1523
  },
  "tool_calls": [
    {
      "tool": "resources/read",
      "arguments": {"uri": "domain://examples/boot-time-report-template"},
      "result": {...},
      "duration_ms": 45
    },
    {
      "tool": "get_key_metrics",
      "arguments": {"os_id": "rhel", "from_timestamp": "last week"},
      "result": {"metric_points": [...]},
      "duration_ms": 1234
    }
  ]
}
```

## Test Queries

### Simple Queries

```bash
# Basic boot time query
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the RHEL boot times?"}'

# With time range
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Show boot times from yesterday"}'

# OS-specific
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Compare RHEL and AutoSD boot performance"}'
```

### Complex Queries (Multi-Step)

```bash
# Should read template, then query data
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Generate a detailed boot time report for RHEL showing all phases and statistics"}'

# Should read glossary, then query
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What boot phases are measured and what do they mean?"}'
```

## Test with Python

```python
import requests
import json

# Configuration
API_URL = "http://localhost:8000/api/query"
TOKEN = "your-test-token"  # if auth enabled

# Test query
def test_query(query: str):
    headers = {
        "Content-Type": "application/json",
        # "Authorization": f"Bearer {TOKEN}",  # uncomment if auth enabled
    }
    
    data = {"query": query}
    
    response = requests.post(API_URL, headers=headers, json=data)
    response.raise_for_status()
    
    result = response.json()
    
    print(f"Query: {result['query']}")
    print(f"\nAnswer:\n{result['answer']}")
    print(f"\nMetadata:")
    print(f"  - Tool calls: {result['metadata']['tool_calls']}")
    print(f"  - LLM calls: {result['metadata']['llm_calls']}")
    print(f"  - Duration: {result['metadata']['duration_ms']}ms")
    print(f"\nTool execution trace:")
    for i, call in enumerate(result['tool_calls'], 1):
        print(f"  {i}. {call['tool']}({json.dumps(call['arguments'])})")
        print(f"     -> {call['duration_ms']}ms")
    
    return result

# Run test
if __name__ == "__main__":
    test_query("Show RHEL boot times for the last week")
```

## Expected Behavior

### 1. First Query (Cold Start)

The LLM should:
1. Read `domain://examples/boot-time-report-template` to understand format
2. Call `get_key_metrics` with appropriate parameters
3. Format the response according to the template

**Watch for:**
- 2-3 tool calls
- 2-3 LLM calls (conversation turns)
- Duration: 2-5 seconds (includes API latency)

### 2. Simple Query (No Resources Needed)

If the query is straightforward:
1. Call `get_key_metrics` directly
2. Format response

**Watch for:**
- 1 tool call
- 2 LLM calls
- Duration: 1-3 seconds

### 3. Error Handling

**Rate Limit (429):**
```json
{
  "error": "LLM API rate limit exceeded",
  "message": "..."
}
```

**LLM Not Configured (503):**
```json
{
  "error": "LLM not configured",
  "message": "Set LLM_PROVIDER, LLM_API_KEY, and LLM_MODEL env vars"
}
```

**Invalid Query (400):**
```json
{
  "error": "Query cannot be empty"
}
```

## Monitoring

### Server Logs

Watch for these log messages:

```
INFO     src.server.http:http.py:1678 api.query.start
         extra={'req_id': '...', 'query': 'Show RHEL...', 'query_length': 33}

INFO     src.llm.orchestrator:orchestrator.py:237 Starting query execution
         extra={'query_preview': 'Show RHEL...'}

INFO     src.llm.orchestrator:orchestrator.py:259 LLM iteration
         extra={'iteration': 1, 'message_count': 2}

INFO     src.llm.orchestrator:orchestrator.py:318 Tool calls found
         extra={'count': 1, 'iteration': 1}

INFO     src.llm.orchestrator:orchestrator.py:334 Tool execution complete
         extra={'tool': 'get_key_metrics', 'duration_ms': 1234, 'iteration': 1}

INFO     src.server.http:http.py:1691 api.query.complete
         extra={'req_id': '...', 'tool_calls': 1, 'llm_calls': 2, 'duration_ms': 1523}
```

### Token Usage

Check logs for token consumption:
```
INFO     src.llm.client:client.py:210 Gemini request complete
         extra={'prompt_tokens': 150, 'completion_tokens': 75, 'total_tokens': 225}
```

## Troubleshooting

### Endpoint Returns 503 "LLM not configured"

**Solution:** Check environment variables:
```bash
echo $LLM_PROVIDER
echo $LLM_API_KEY
echo $LLM_MODEL
```

Restart server after setting them.

### Rate Limit Errors

**Solution:** 
- Use `gemini-1.5-flash` (higher rate limits than pro)
- Add delays between requests
- Check your API quota at https://aistudio.google.com/app/apikey

### LLM Not Calling Tools

**Symptom:** Response is generic or says "I cannot help with that"

**Possible Causes:**
1. System prompt not emphasizing tool execution
2. LLM misunderstanding the query
3. Temperature too high (set to 0.1 for deterministic)

**Debug:** Check `tool_calls` array in response - should not be empty

### Max Iterations Reached

**Symptom:** Response says "reached maximum number of iterations"

**Cause:** LLM stuck in loop calling tools repeatedly

**Solution:** 
- Simplify query
- Check if tools are returning useful data
- Increase `max_iterations` in orchestrator (default: 10)

## Performance Expectations

| Query Type | Tool Calls | LLM Calls | Duration | Tokens |
|------------|-----------|-----------|----------|--------|
| Simple     | 1         | 2         | 1-3s     | 200-400 |
| Complex    | 2-3       | 3-4       | 3-5s     | 400-800 |
| With errors| 1-2       | 2-3       | 2-4s     | 300-500 |

**Note:** First request may be slower due to model initialization.

## Next Steps

After functional testing validates the endpoint works:
1. Test with various query patterns
2. Document failure cases
3. Refine system prompt if needed
4. Add integration tests
5. Proceed to Phase 6.3: Production Readiness

## Questions or Issues?

- Check server logs for detailed trace
- Review `domain_mcp_development_plan.md` Phase 6 documentation
- See `docs/query-failures.md` for known query patterns

