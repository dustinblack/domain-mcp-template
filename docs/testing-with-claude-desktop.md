# Testing Your Domain MCP with Claude Desktop

Once your Domain MCP server is running, you need to connect it to Claude Desktop to test real-world queries in Phase 5.

## Prerequisites

- [ ] Your Domain MCP server can start without errors
- [ ] Source MCP connection is working (`python scripts/verify_connection.py` passes)
- [ ] Plugin extracts metrics correctly (unit tests pass)
- [ ] Glossary files are complete and valid JSON

---

## Step 1: Install Claude Desktop

**Download:** https://claude.ai/download

**Supported platforms:**
- macOS 10.15+
- Windows 10+
- Linux (AppImage)

**Install and launch** Claude Desktop before proceeding.

---

## Step 2: Configure Your Domain MCP

Claude Desktop needs to know how to launch and connect to your MCP server.

### Find Your Configuration File

**macOS:** 
```bash
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:** 
```bash
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux:** 
```bash
~/.config/Claude/claude_desktop_config.json
```

### Create or Edit Configuration

If the file doesn't exist, create it. Then add your Domain MCP server configuration:

```json
{
  "mcpServers": {
    "your-domain-mcp": {
      "command": "python",
      "args": [
        "-m", "src.server.cli", "run",
        "--host", "0.0.0.0",
        "--port", "8000"
      ],
      "cwd": "/absolute/path/to/your/domain-mcp",
      "env": {
        "PYTHONPATH": "/absolute/path/to/your/domain-mcp",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**Important configuration notes:**

1. **Replace `your-domain-mcp`** with a descriptive name for your server
   - Examples: `webperf-mcp`, `payment-analytics-mcp`, `api-monitoring-mcp`

2. **Replace `/absolute/path/to/your/domain-mcp`** with your actual project path
   - Use full absolute paths (not relative like `~/` or `./`)
   - Example macOS: `/Users/yourname/projects/webperf-mcp`
   - Example Windows: `C:\\Users\\yourname\\projects\\webperf-mcp`
   - Example Linux: `/home/yourname/projects/webperf-mcp`

3. **Python command:** If using a virtual environment:
   ```json
   "command": "/absolute/path/to/your/venv/bin/python"
   ```

4. **Environment variables:** Add any needed for your Source MCP:
   ```json
   "env": {
     "PYTHONPATH": "/absolute/path/to/your/domain-mcp",
     "LOG_LEVEL": "DEBUG",
     "ES_API_KEY": "your-es-key-if-needed"
   }
   ```

### Example Configuration (Web Performance MCP)

```json
{
  "mcpServers": {
    "webperf-mcp": {
      "command": "/Users/alice/projects/webperf-mcp/.venv/bin/python",
      "args": [
        "-m", "src.server.cli", "run",
        "--host", "127.0.0.1",
        "--port", "8000"
      ],
      "cwd": "/Users/alice/projects/webperf-mcp",
      "env": {
        "PYTHONPATH": "/Users/alice/projects/webperf-mcp",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

---

## Step 3: Restart Claude Desktop

**Important:** Claude only loads MCP configuration at startup.

1. **Quit** Claude Desktop completely (not just close window)
   - macOS: `Cmd+Q` or Claude → Quit
   - Windows: Right-click system tray icon → Exit
   - Linux: Use your desktop's quit/close application method

2. **Relaunch** Claude Desktop

3. **Wait** for startup to complete (10-15 seconds)

---

## Step 4: Verify Connection

In Claude Desktop, start a new conversation and ask:

```
What MCP servers are available?
```

**Expected response:** Claude should list your Domain MCP server:
```
I can see the following MCP servers:
- your-domain-mcp (connected)
```

**If not listed:** → See Troubleshooting section below

---

## Step 5: Load Your Domain Glossary

Tell Claude to read your domain glossary so it understands your terminology:

```
Please read all the glossary resources from my Domain MCP to understand my domain terminology.
```

**Expected behavior:**
- Claude will invoke the `resources/list` tool
- Claude will read each glossary file (KPIs, dimensions)
- Claude should acknowledge: "I've read your domain glossary covering [X] KPIs and [Y] dimensions"

**Verify Claude understood:**
```
What KPIs are available in my domain?
```

Claude should list your metrics from the glossary.

---

## Step 6: Test Your Queries

Now test your real-world queries from Phase 5.1. Start with simple queries:

### Simple Query Test
```
Show me page load time for today
```

**What to observe:**
1. Claude should invoke `get_key_metrics` tool
2. Parameters should include:
   - `metric_name: "page_load_time"`
   - `start_time`: Today's date
   - `end_time`: Now
3. Results should be returned and formatted by Claude

### Medium Complexity Test
```
What's the p95 API latency in APAC for the last 7 days?
```

**What to observe:**
1. Claude should extract:
   - Metric: `api_latency`
   - Aggregation: `p95`
   - Filter: `region=apac`
   - Time range: Last 7 days
2. Results should be filtered correctly

### Complex Query Test
```
Compare checkout page load time between mobile and desktop users over the past week
```

**What to observe:**
1. Claude may make multiple `get_key_metrics` calls
2. Once for `device_class=mobile`, once for `device_class=desktop`
3. Claude should synthesize a comparison

---

## Phase 5 Testing Workflow

Follow this workflow for systematic query validation:

### 1. Start Your Session

**Terminal 1 (Server logs):**
```bash
cd /path/to/your/domain-mcp
export LOG_LEVEL=DEBUG
python -m src.server.cli run --host 0.0.0.0 --port 8000
```

**Keep this terminal visible** to watch server logs in real-time.

**Claude Desktop:** 
- Launch and start new conversation
- Prime with: "Read my domain glossary from my Domain MCP"

---

### 2. Test Each Query

For each query in your `docs/example_queries.md`:

1. **Ask the query** in natural language
2. **Watch server logs** for `get_key_metrics` invocation
3. **Check parameters** passed to the tool
4. **Verify results** match expectations
5. **Document outcome** in your example_queries.md:
   - ✅ Works perfectly
   - ⚠️ Partially works (note what's wrong)
   - ❌ Fails (note error or unexpected behavior)

---

### 3. Debug Failures

If a query doesn't work:

1. **Check what Claude understood:**
   ```
   What parameters did you just pass to get_key_metrics?
   ```

2. **Check server logs** for:
   - Was the tool invoked?
   - What parameters were received?
   - Did the adapter fetch data?
   - Did the plugin extract metrics?

3. **Follow the debugging decision tree** in `IMPLEMENTATION_PLAN.md` Phase 5.3.3

---

### 4. Fix Issues

Based on failures:

**LLM didn't understand term:**
- Add to glossary with more examples and synonyms
- Restart server
- Ask Claude to re-read glossary

**Wrong parameter extracted:**
- Update glossary with clearer examples
- Add to `example_queries` field

**No data returned:**
- Check Source MCP connection
- Verify time range has data
- Check filters aren't too restrictive

**Wrong results:**
- Check plugin extraction logic
- Verify unit conversions
- Check dimension mappings

---

### 5. Iterate

1. Make fixes to glossary/plugin/adapter
2. Restart server
3. Retest failed queries
4. Update `docs/example_queries.md` with new status
5. Repeat until 80%+ queries work correctly

---

## Troubleshooting

### "MCP server not found" or not listed

**Symptom:** Claude doesn't list your MCP server when asked

**Solutions:**

1. **Check config file location:**
   ```bash
   # macOS
   cat ~/Library/Application\ Support/Claude/claude_desktop_config.json
   
   # Linux
   cat ~/.config/Claude/claude_desktop_config.json
   ```
   Verify file exists and is valid JSON

2. **Validate JSON syntax:**
   ```bash
   # Use Python to validate
   python -m json.tool < claude_desktop_config.json
   ```
   If errors, fix JSON syntax (missing commas, quotes, etc.)

3. **Check paths are absolute:**
   - ❌ `"cwd": "~/projects/mcp"` (tilde doesn't work)
   - ❌ `"cwd": "./mcp"` (relative path doesn't work)
   - ✅ `"cwd": "/Users/alice/projects/mcp"` (absolute path)

4. **Verify Python command works:**
   ```bash
   # Test if command in config actually works
   cd /absolute/path/to/your/domain-mcp
   python -m src.server.cli run --host 0.0.0.0 --port 8000
   ```
   Should start without errors

5. **Restart Claude completely:**
   - Quit (not just close window)
   - Wait 5 seconds
   - Relaunch

---

### "Connection refused" or "Server not responding"

**Symptom:** MCP is listed but Claude can't connect

**Solutions:**

1. **Ensure server can start:**
   ```bash
   python -m src.server.cli run --host 0.0.0.0 --port 8000
   ```
   Should show: `"Server started on http://0.0.0.0:8000"`

2. **Check port isn't blocked:**
   ```bash
   # Test if port 8000 is available
   lsof -i :8000  # macOS/Linux
   netstat -ano | findstr :8000  # Windows
   ```
   If port is in use, change to different port in config

3. **Verify Source MCP connection:**
   ```bash
   python scripts/verify_connection.py
   ```
   Must pass before Claude can use your server

4. **Check config.json exists:**
   ```bash
   ls -la config.json
   ```
   Your Domain MCP needs its own config.json with Source MCP details

5. **Check firewall:**
   - Ensure localhost connections allowed
   - Add exception for Python if needed

---

### "Tool not found" or `get_key_metrics` not available

**Symptom:** Claude connects but doesn't show tool

**Solutions:**

1. **Check tool registration:**
   ```bash
   # Look for tool registration in logs
   python -m src.server.cli run | grep "Registered tool"
   ```
   Should show: `"Registered tool: get_key_metrics"`

2. **Verify server mode:**
   - Ensure running in MCP mode (not HTTP-only mode)
   - Check `src/server/cli.py` has tool definitions

3. **Ask Claude to list tools:**
   ```
   What tools do you have access to from my Domain MCP?
   ```
   Should list `get_key_metrics` with parameters

---

### Claude doesn't understand domain terms

**Symptom:** Claude makes wrong `get_key_metrics` calls

**Solutions:**

1. **Verify glossary files exist:**
   ```bash
   ls -la src/resources/glossary/
   # Should show: *_kpis.json, *_dimensions.json
   ```

2. **Validate glossary JSON:**
   ```bash
   python -m json.tool < src/resources/glossary/my_kpis.json
   ```
   Must be valid JSON

3. **Check glossary is registered as resource:**
   - Look in `src/server/` for resource registration
   - Glossary files should be exposed via MCP resources

4. **Explicitly ask Claude to read it:**
   ```
   Please read the glossary resources from my Domain MCP server:
   - Read my_domain_kpis.json
   - Read my_domain_dimensions.json
   Tell me what KPIs and dimensions you understand.
   ```

5. **Verify glossary completeness:**
   - Use the scoring system in IMPLEMENTATION_PLAN.md Phase 3.1.4
   - Ensure minimum 3 example queries per KPI
   - Ensure minimum 2 synonyms for acronyms

---

### Queries are slow (>30 seconds)

**Symptom:** Claude waits long time for responses

**Solutions:**

1. **Check data volume:**
   - How many documents are being fetched?
   - Reduce time range: "last 7 days" instead of "last 90 days"
   - Add limit to adapter: max 1000 documents per query

2. **Use source-side aggregation:**
   - Let Elasticsearch do aggregation (faster)
   - Instead of fetching 10k documents and aggregating in Python

3. **Check Source MCP performance:**
   - Is Elasticsearch slow?
   - Are indexes optimized?
   - Consider adding caching

4. **Add query defaults in config.json:**
   ```json
   {
     "query_defaults": {
       "max_results_per_query": 1000,
       "timeout_seconds": 30
     }
   }
   ```

---

### Results don't match expectations

**Symptom:** Claude returns data but values seem wrong

**Solutions:**

1. **Enable debug logging:**
   ```bash
   export LOG_LEVEL=DEBUG
   python -m src.server.cli run
   ```

2. **Check raw data:**
   - Look at documents fetched from Source MCP
   - Are values in source correct?

3. **Verify unit conversion:**
   - Check plugin converts ms ↔ s correctly
   - Check bytes ↔ KB/MB correctly

4. **Test plugin in isolation:**
   ```bash
   python scripts/test_plugin.py \
     --plugin your-plugin \
     --sample tests/fixtures/your-domain/source_sample.json \
     --verbose
   ```

5. **Use query debugging decision tree:**
   - See IMPLEMENTATION_PLAN.md Phase 5.3.3
   - Follow step-by-step diagnosis

---

## Tips for Better Results

### Prime Claude with Context

Start your conversation with context about your domain:

```
I'm working with web performance metrics stored in Elasticsearch. 
I'll be asking you questions about page load times, API latency, 
and error rates across different regions and device types. 

Please read the glossary from my Domain MCP to understand these terms,
then I'll ask you some queries.
```

### Be Specific in Queries

**Good queries (specific):**
- ✅ "Show me p95 page load time in APAC for the last 7 days"
- ✅ "What's the error rate for checkout API in production?"
- ✅ "Compare mobile vs desktop TTFB over the past week"

**Vague queries (may fail):**
- ❌ "How's performance?"
- ❌ "Show me some data"
- ❌ "Are there any issues?"

### Check What Claude Understood

After getting results, verify the interpretation:

```
What parameters did you pass to get_key_metrics just now?
```

This helps you understand:
- What metric Claude selected
- What filters were applied
- What time range was used

Then you can refine your glossary if needed.

### Iterate on Phrasing

If a query doesn't work, try different phrasing:

- "Show me page load time" vs "What's the page load time"
- "in APAC" vs "for APAC region" vs "APAC performance"
- "last week" vs "past 7 days" vs "7 days ago to now"

Document which phrasings work best in your glossary's `example_queries`.

### Use Multiple Sessions

For comprehensive testing:

1. **Fresh session:** Test if glossary is sufficient without priming
2. **Primed session:** Provide extra context, see if queries work better
3. **Iterative session:** Make fixes, retest in same conversation

Compare results to see if glossary needs more examples.

---

## Phase 5 Completion Criteria

Before proceeding to Phase 6 (Deployment), ensure:

- [ ] 80%+ of your real-world queries work correctly
- [ ] Query response times are acceptable (< 30s for complex queries)
- [ ] Results are accurate and match manual verification
- [ ] `docs/example_queries.md` is complete with working queries
- [ ] Team members can use your documented queries successfully
- [ ] Edge cases handled gracefully (no crashes on unexpected queries)

**If criteria not met:** Iterate on glossary, plugin, and filters until achieved.

---

## Next Steps

Once testing is successful:

1. **Document working queries** in `docs/example_queries.md`
2. **Share with team** for feedback
3. **Proceed to Phase 6** (Deployment) in IMPLEMENTATION_PLAN.md
4. **Set up monitoring** for production usage
5. **Plan for ongoing maintenance** (adding new KPIs, dimensions)

---

## Additional Resources

- **IMPLEMENTATION_PLAN.md Phase 5:** Complete query validation workflow
- **IMPLEMENTATION_PLAN.md Phase 5.3.3:** Query debugging decision tree
- **docs/example_queries.md:** Template for documenting queries
- **README.md Troubleshooting:** Common connection and plugin issues

---

## Quick Reference Commands

```bash
# Validate Claude config
python -m json.tool < ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Start server with debug logging
export LOG_LEVEL=DEBUG
python -m src.server.cli run --host 0.0.0.0 --port 8000

# Test plugin in isolation
python scripts/test_plugin.py --plugin your-plugin --sample tests/fixtures/your-domain/source_sample.json

# Verify Source MCP connection
python scripts/verify_connection.py

# Validate glossary JSON
python -m json.tool < src/resources/glossary/your_kpis.json
```

