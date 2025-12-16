# LLM Integration Guide

Complete guide to the natural language query endpoint powered by LLM 
orchestration.

## Overview

The `/api/query` endpoint provides direct natural language access to your domain data without requiring MCP protocol setup. It uses an LLM (currently Google Gemini, with multi-provider support planned) to:

1. **Understand** natural language questions
2. **Orchestrate** Domain MCP tools (get_key_metrics, resources/read)
3. **Format** results into readable answers

**Key Benefits:**
- 🚀 Simple HTTP API - no MCP client setup required
- 🔒 Production-ready with rate limiting and token tracking
- 🛡️ Input validation and prompt injection protection
- 📊 Built-in usage monitoring and cost tracking

## Quick Start

### 1. Get a Gemini API Key

Visit [Google AI Studio](https://aistudio.google.com/app/apikey) and create a 
free API key.

### 2. Configure Environment Variables

```bash
# Required
export DOMAIN_MCP_LLM_PROVIDER=gemini
export DOMAIN_MCP_LLM_API_KEY=your-gemini-api-key-here
export DOMAIN_MCP_LLM_MODEL=gemini-2.5-flash

# Optional (with sensible defaults)
export DOMAIN_MCP_LLM_TEMPERATURE=0.1  # Lower = more deterministic
export DOMAIN_MCP_LLM_MAX_TOKENS=4096  # Max response length
```

### 3. Start the Server

```bash
python -m src.server.cli --http --port 8080
```

### 4. Test It

```bash
curl -X POST http://localhost:8080/api/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "Show metrics for [your domain filter] over the last week"}'
# Example (PerfScale): "Show RHEL boot times for the last week"
```

## Architecture

### Request Flow

```
Client Request
     ↓
[Input Validation]
     ↓
[Rate Limit Check]
     ↓
[LLM Orchestrator] ← System Prompt (Domain Knowledge)
     ↓
[Parse Tool Calls] → Execute MCP Tools → Format Results
     ↓
[Response + Metadata]
```

### Components

**LLM Client** (`src/llm/client.py`):
- Multi-provider abstraction (Gemini, OpenAI, Anthropic planned)
- Token usage tracking
- Error handling and retries
- Endpoint configuration (public/corporate)

**Query Orchestrator** (`src/llm/orchestrator.py`):
- Conversation management
- Tool call parsing (`TOOL_CALL: {"name": "...", "arguments": {...}}`)
- Iterative execution (multi-turn conversations)
- Result formatting

**Rate Limiter** (`src/server/rate_limiter.py`):
- Per-client sliding window limits
- Request and token quotas
- Admin bypass for testing

**HTTP Endpoint** (`src/server/http.py`):
- POST `/api/query`
- Authentication (bearer token)
- Input validation
- Response formatting

## Configuration

### LLM Provider Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DOMAIN_MCP_LLM_PROVIDER` | `None` | Provider: `gemini`, `openai` (planned), `anthropic` (planned) |
| `DOMAIN_MCP_LLM_API_KEY` | `None` | API key for the LLM provider (required) |
| `DOMAIN_MCP_LLM_MODEL` | `None` | Model name (e.g., `gemini-2.5-flash`, `gemini-1.5-flash`) |
| `DOMAIN_MCP_LLM_TEMPERATURE` | `0.1` | Temperature (0.0-1.0): Lower = more deterministic |
| `DOMAIN_MCP_LLM_MAX_TOKENS` | `4096` | Maximum tokens per LLM response (1-32768) |
| `DOMAIN_MCP_LLM_MAX_ITERATIONS` | `10` | Max orchestration iterations (1-100): Increase for complex multi-step queries |

### Gemini-Specific Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DOMAIN_MCP_LLM_GEMINI_ENDPOINT` | `None` | Custom endpoint for Vertex AI/corporate instances |
| `DOMAIN_MCP_LLM_GEMINI_PROJECT` | `None` | Google Cloud project ID for Vertex AI billing |

**Example: Using Vertex AI**
```bash
export DOMAIN_MCP_LLM_PROVIDER=gemini
export DOMAIN_MCP_LLM_GEMINI_ENDPOINT=https://us-central1-aiplatform.googleapis.com
export DOMAIN_MCP_LLM_GEMINI_PROJECT=my-gcp-project-id
export DOMAIN_MCP_LLM_API_KEY=your-vertex-ai-key
export DOMAIN_MCP_LLM_MODEL=gemini-2.5-flash
```

### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `DOMAIN_MCP_RATE_LIMIT_ENABLED` | `true` | Enable/disable rate limiting |
| `DOMAIN_MCP_RATE_LIMIT_REQUESTS_PER_HOUR` | `100` | Max requests per client per hour |
| `DOMAIN_MCP_RATE_LIMIT_TOKENS_PER_HOUR` | `100000` | Max tokens per client per hour |
| `DOMAIN_MCP_RATE_LIMIT_ADMIN_KEY` | `None` | Bypass key for testing/debugging |

**Client Identification:**
Clients are identified by IP address (`request.client.host`). In production 
behind a proxy, ensure `X-Forwarded-For` headers are properly configured.

**Rate Limit Response:**
```json
{
  "detail": {
    "error": "Rate limit exceeded",
    "message": "Request rate limit exceeded (100 requests/hour). Retry after 3421 seconds."
  }
}
```

**Admin Bypass:**
```bash
# Set admin key
export DOMAIN_MCP_RATE_LIMIT_ADMIN_KEY=your-secret-admin-key

# Use in request (not recommended for production)
curl -X POST http://localhost:8080/api/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "...", "admin_key": "your-secret-admin-key"}'
```

### Input Validation

| Variable | Default | Description |
|----------|---------|-------------|
| `DOMAIN_MCP_QUERY_MAX_LENGTH` | `2000` | Maximum query length (100-10000 characters) |

**Blocked Patterns:**
- Null bytes (`\x00`)
- Prompt injection attempts (`IGNORE PREVIOUS`, `IGNORE ALL`, `SYSTEM:`)
- Model control tokens (`</s>`, `<|endoftext|>`)

## API Reference

### Endpoint

```
POST /api/query
```

### Request

**Headers:**
- `Content-Type: application/json`
- `Authorization: Bearer <token>` (if `DOMAIN_MCP_HTTP_TOKEN` is set)

**Body:**
```json
{
  "query": "Your natural language question here"
}
```

**Example:**
```bash
curl -X POST http://localhost:8080/api/query \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer your-token-here' \
  -d '{"query": "Show metrics for [your domain filter] over the last week"}'
```

### Response

**Success (200 OK):**
```json
{
  "query": "Show metrics for [your domain filter] over the last week",
  "answer": "Based on analysis of data from the past week...",
  "metadata": {
    "tool_calls": 1,
    "llm_calls": 2,
    "duration_ms": 3421,
    "total_tokens": 1523,
    "rate_limit": {
      "client_id": "127.0.0.1",
      "requests_remaining": 99,
      "requests_limit": 100,
      "tokens_remaining": 98477,
      "tokens_limit": 100000,
      "window_seconds": 3600
    }
  },
  "tool_calls": [
    {
      "tool": "get_key_metrics",
      "arguments": {"os_id": "rhel", "from_timestamp": "last week"},
      "result": {...},
      "duration_ms": 2103
    }
  ]
}
```

**Error Responses:**

**400 Bad Request** (Invalid input):
```json
{
  "detail": {
    "error": "Query too long",
    "max_length": 2000,
    "actual_length": 3500
  }
}
```

**429 Too Many Requests** (Rate limit):
```json
{
  "detail": {
    "error": "Rate limit exceeded",
    "message": "Token budget exceeded (100000 tokens/hour). Retry after 1234 seconds."
  }
}
```

**503 Service Unavailable** (LLM not configured):
```json
{
  "detail": {
    "error": "LLM not configured",
    "message": "Set LLM_PROVIDER, LLM_API_KEY, and LLM_MODEL to enable /api/query endpoint"
  }
}
```

## Usage Examples

### Basic Query

```bash
curl -X POST http://localhost:8080/api/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "What is the average boot time for RHEL?"}'
```

### Time-Filtered Query

```bash
curl -X POST http://localhost:8080/api/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "Show boot times from yesterday"}'
```

### Statistical Analysis

```bash
curl -X POST http://localhost:8080/api/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "Give me p95 and p99 boot times for nightly runs"}'
```

### Comparison Query

```bash
curl -X POST http://localhost:8080/api/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "Compare RHEL and AutoSD boot times"}'
```

## Monitoring and Observability

### Log Levels

```bash
# INFO: Request/response logging, token usage
python -m src.server.cli --http --log-level INFO

# DEBUG: Detailed LLM responses, tool calls, iterations
python -m src.server.cli --http --log-level DEBUG
```

### Key Log Events

**Query Start:**
```
INFO src.server.http - api.query.start
  req_id=abc123
  client_id=127.0.0.1
  query=Show RHEL boot times...
  query_length=42
```

**Query Complete:**
```
INFO src.server.http - api.query.complete
  req_id=abc123
  client_id=127.0.0.1
  tool_calls=1
  llm_calls=2
  duration_ms=3421
  total_tokens=1523
  tokens_remaining=98477
```

**Rate Limit Warning:**
```
WARNING src.server.http - Rate limit exceeded
  req_id=abc123
  client_id=192.168.1.100
  error=Request rate limit exceeded...
```

### Token Usage Tracking

Monitor token consumption in logs:

```bash
# Extract token usage from logs
grep "api.query.complete" server.log | jq '.total_tokens'

# Track per-client token usage
grep "api.query.complete" server.log | jq '{client: .client_id, tokens: .total_tokens}'
```

## Troubleshooting

### Endpoint Returns 404

**Symptom:** `/api/query` endpoint not found

**Cause:** LLM not configured

**Solution:**
```bash
# Check startup logs
grep "LLM" server.log

# Expected: "LLM provider not configured, LLM features disabled"
# Set required env vars and restart
export DOMAIN_MCP_LLM_PROVIDER=gemini
export DOMAIN_MCP_LLM_API_KEY=your-key
export DOMAIN_MCP_LLM_MODEL=gemini-2.5-flash
```

### Rate Limit Exceeded Immediately

**Symptom:** 429 errors on first request

**Cause:** Multiple clients sharing same IP or misconfigured limits

**Solution:**
```bash
# Increase limits
export DOMAIN_MCP_RATE_LIMIT_REQUESTS_PER_HOUR=1000
export DOMAIN_MCP_RATE_LIMIT_TOKENS_PER_HOUR=1000000

# Or disable temporarily for testing
export DOMAIN_MCP_RATE_LIMIT_ENABLED=false
```

### LLM Returns Tool Calls as Text

**Symptom:** Response contains `TOOL_CALL: {...}` in the answer

**Cause:** Tool call parsing regex failure (should be fixed in Phase 6.2)

**Solution:** Update to latest version with regex fix

### High Token Usage

**Symptom:** Rapid token consumption

**Causes & Solutions:**

1. **Long conversations:** Multi-turn queries accumulate tokens
   - Solution: Use simpler, direct questions

2. **Large responses:** Verbose LLM outputs
   - Solution: Lower `DOMAIN_MCP_LLM_MAX_TOKENS`

3. **High temperature:** More exploratory responses
   - Solution: Lower `DOMAIN_MCP_LLM_TEMPERATURE` (try 0.0-0.1)

4. **Inefficient prompts:** Poor system prompt
   - Note: Phase 6.1 uses minimal prompt (~150 tokens), relies on MCP Resources

### Gemini API Errors

**429 Quota Exceeded:**
```
Quota exceeded for metric: generativelanguage.googleapis.com/generate_requests_per_model_per_day
```

**Solutions:**
- Switch to `gemini-1.5-flash` (higher free tier)
- Wait for quota reset (midnight UTC)
- Upgrade to paid tier
- Get new API key

**401 Invalid API Key:**
```
API key not valid. Please pass a valid API key.
```

**Solutions:**
- Verify key at https://aistudio.google.com/app/apikey
- Check environment variable is set correctly
- Ensure key has no trailing spaces/newlines

## Security Considerations

### API Key Protection

**DO:**
- Store in environment variables
- Use secrets management (Kubernetes secrets, Vault)
- Rotate keys regularly
- Use separate keys for dev/staging/prod

**DON'T:**
- Commit keys to git
- Log keys in plain text
- Share keys between environments
- Use keys in client-side code

### Rate Limiting

**Purpose:**
- Prevent abuse and cost runaway
- Ensure fair resource allocation
- Protect against DoS attacks

**Best Practices:**
- Enable in production (`DOMAIN_MCP_RATE_LIMIT_ENABLED=true`)
- Set conservative limits initially
- Monitor usage patterns
- Adjust based on actual needs

### Input Validation

**Built-in Protections:**
- Query length limits (prevent resource exhaustion)
- Prompt injection detection (prevent LLM manipulation)
- Model control token blocking (prevent jailbreaks)

**Additional Recommendations:**
- Use authentication (`DOMAIN_MCP_HTTP_TOKEN`)
- Deploy behind reverse proxy
- Enable request logging
- Monitor for suspicious patterns

## Cost Management

### Gemini Pricing (as of 2025)

**Free Tier:**
- 15 requests per minute
- 1,500 requests per day
- Rate limits vary by model

**Paid Tier:**
- `gemini-1.5-flash`: ~$0.10 per 1M tokens
- `gemini-1.5-pro`: ~$3.50 per 1M tokens

### Cost Estimation

```python
# Rough estimate
average_tokens_per_query = 1500  # prompt + completion + tool results
queries_per_day = 1000
cost_per_million_tokens = 0.10  # gemini-1.5-flash

daily_tokens = average_tokens_per_query * queries_per_day
daily_cost = (daily_tokens / 1_000_000) * cost_per_million_tokens
monthly_cost = daily_cost * 30

# Result: ~$0.045/day, ~$1.35/month for 1000 queries/day
```

### Cost Optimization

1. **Use efficient models:** `gemini-1.5-flash` vs `gemini-1.5-pro`
2. **Lower temperature:** Reduce exploratory behavior
3. **Limit max tokens:** Cap response length
4. **Cache results:** Implement query caching (Phase 6.4 planned)
5. **Rate limits:** Enforce token budgets per client
6. **Optimize prompts:** Minimal system prompt (already done in Phase 6.1)

### Budget Enforcement

```bash
# Set strict token limits
export DOMAIN_MCP_RATE_LIMIT_TOKENS_PER_HOUR=10000  # ~$0.001/hour

# Monitor usage
grep "total_tokens" server.log | awk '{sum+=$NF} END {print "Total tokens: " sum}'

# Calculate cost
total_tokens=$(grep "total_tokens" server.log | awk '{sum+=$NF} END {print sum}')
cost=$(echo "scale=4; $total_tokens / 1000000 * 0.10" | bc)
echo "Estimated cost: \$$cost"
```

## Future Enhancements (Phase 6.4)

Planned features for future releases:

- **Multi-provider support:** OpenAI, Anthropic (Claude), Azure OpenAI
- **Streaming responses:** SSE for real-time feedback
- **Query caching:** 24h TTL for identical queries
- **Conversation persistence:** Multi-turn sessions across requests
- **Query templates:** Pre-defined patterns for common use cases
- **Advanced analytics:** Cost tracking per user/project
- **Response formatting:** Markdown, JSON, tables

## Reference

### Related Documentation

- [Quick Start Guide](quickstart.md) - 5-minute setup
- [Functional Testing Guide](llm-query-testing.md) - Test your deployment
- [API Documentation](api/) - Complete API reference
- [Troubleshooting Guide](troubleshooting.md) - Common issues

### Source Code

- `src/llm/client.py` - LLM client implementations
- `src/llm/orchestrator.py` - Query orchestration logic
- `src/llm/prompts.py` - System prompts
- `src/server/rate_limiter.py` - Rate limiting
- `src/server/http.py` - `/api/query` endpoint
- `src/config/models.py` - Configuration models

### Environment Variables Reference

All LLM-related environment variables use the `DOMAIN_MCP_` prefix:

```bash
# LLM Provider
DOMAIN_MCP_LLM_PROVIDER=gemini
DOMAIN_MCP_LLM_API_KEY=your-key
DOMAIN_MCP_LLM_MODEL=gemini-2.5-flash
DOMAIN_MCP_LLM_TEMPERATURE=0.1
DOMAIN_MCP_LLM_MAX_TOKENS=4096
DOMAIN_MCP_LLM_GEMINI_ENDPOINT=https://...
DOMAIN_MCP_LLM_GEMINI_PROJECT=project-id

# Rate Limiting
DOMAIN_MCP_RATE_LIMIT_ENABLED=true
DOMAIN_MCP_RATE_LIMIT_REQUESTS_PER_HOUR=100
DOMAIN_MCP_RATE_LIMIT_TOKENS_PER_HOUR=100000
DOMAIN_MCP_RATE_LIMIT_ADMIN_KEY=secret

# Input Validation
DOMAIN_MCP_QUERY_MAX_LENGTH=2000
```

## Support

**Issues:** Report bugs via GitHub Issues
**Questions:** See [Troubleshooting Guide](troubleshooting.md)
**Contributing:** See [CONTRIBUTING.md](../CONTRIBUTING.md)

