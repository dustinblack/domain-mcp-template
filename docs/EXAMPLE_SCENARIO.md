# Example Implementation Scenario: WebPerf Monitor MCP

> **Purpose:** This document walks through a realistic implementation scenario to help first-time users understand the end-to-end process of building a Domain MCP server. Use this alongside the `IMPLEMENTATION_PLAN.md` to see what the journey actually looks like.

![Example Scenario Overview](EXAMPLE_SCENARIO.png)

---

## 🎭 Meet Sarah: The Performance Engineer

**Background:**
- Senior Performance Engineer at "ShopFast", a mid-size e-commerce company
- Tests checkout flow, product pages, and search functionality
- Stores 2 years of performance data in Elasticsearch
- Uses Web Vitals terminology: TTFB, LCP, FCP, CLS
- Team communicates with phrases like "APAC is slow again" or "checkout p95 is spiking"

**The Pain Point:**
Sarah spends 30 minutes every morning writing Kibana queries to answer questions like:
- "How's checkout performance in APAC compared to last week?"
- "What's the p95 Time to First Byte for the homepage?"
- "Are we meeting our 500ms TTFB SLO?"

**Discovery:**
Sarah hears about Model Context Protocol and discovers this Domain MCP template on GitHub. She's excited but cautious.

**Her Knowledge Level:**
- ✅ Expert in web performance metrics and Elasticsearch
- ✅ Comfortable with Python, JSON, and Docker
- ⚠️ Just learned about MCP last week (very new concept)
- ⚠️ Never heard of "Domain-Source model" before
- ❌ No MCP server development experience

---

## 📖 Phase-by-Phase Journey

### Phase 0: Understanding the Architecture

**First Confusion: "What's a Source MCP?"**

Sarah reads the README and sees this diagram:
```
Client (Claude) → Domain MCP → Source MCP → Data Source (Elasticsearch)
```

**Her "Aha!" Moment:**
- "The Elasticsearch MCP is pre-built! It's like a generic database driver."
- "MY code (Domain MCP) adds the web performance expertise on top."
- "So I don't have to write Elasticsearch queries - the Source MCP does that!"

**Second Decision: stdio vs HTTP mode**

Sarah checks the connection mode table:
- Her situation: Corporate VPN, Elasticsearch at `es-prod.shopfast.internal:9200`
- Problem: Docker networking often fails with internal DNS on VPNs
- **Decision:** Use HTTP mode - run Elasticsearch MCP as a separate service

---

### Phase 1: Project Initialization (45 minutes)

**Sarah's Actions:**
```bash
git clone https://github.com/dustinblack/domain-mcp-template.git webperf-mcp
cd webperf-mcp
```

Opens in Cursor IDE and prompts AI:
> "I am starting a new project using this template. Please read IMPLEMENTATION_PLAN.md and guide me through the process."

**Project Identity (AI-assisted):**
- **Name:** `webperf-mcp`
- **Domain:** "E-commerce Web Performance Monitoring"  
- **Source:** Elasticsearch
- **Description:** "Monitor page load times, API latency, and Web Vitals for ShopFast platform"

**Cleanup:**
- ❌ Remove `src/adapters/horreum.py` (not using Horreum)
- ❌ Remove `src/domain/examples/horreum_boot_time.py`
- ✅ Keep `src/domain/examples/elasticsearch_logs.py` as reference
- Update README and version strings

**Confusion Point #1: Keep or Delete Examples?**
- **Question:** "Should I delete the boot_time example now or later?"
- **Resolution:** Keep in `examples/` as reference, remove at the end (Phase 6)

---

### Phase 2: Configuration & Connection (90 minutes)

**Setting up Elasticsearch MCP**

Sarah's Elasticsearch version: 8.12 (needs standalone Docker-based MCP)

**First attempt - stdio mode:**
```json
{
  "sources": {
    "elasticsearch-prod": {
      "type": "stdio",
      "command": "docker",
      "args": ["run", "-i", "--rm", 
               "-e", "ES_URL=http://es-prod.shopfast.internal:9200",
               "docker.elastic.co/mcp/elasticsearch", "stdio"]
    }
  }
}
```

**❌ Connection Failed:**
```
ConnectionError: Docker container cannot reach es-prod.shopfast.internal
```

**Confusion Point #2: Network Issues (Time Lost: 30 minutes)**
- **Problem:** Docker container can't resolve internal DNS on corporate VPN
- **Debugging:** Tried `--network host`, still failed
- **Resolution:** Switch to HTTP mode with separate container

**Working Solution - HTTP mode:**

Create `docker-compose.yml`:
```yaml
version: '3.8'
services:
  elasticsearch-mcp:
    image: docker.elastic.co/mcp/elasticsearch
    environment:
      - ES_URL=http://es-prod.shopfast.internal:9200
      - ES_API_KEY=${ES_API_KEY}
    ports:
      - "3000:3000"
    command: ["http", "--port", "3000"]
    network_mode: host  # Allows access to corporate DNS
```

Update `config.json`:
```json
{
  "sources": {
    "elasticsearch-prod": {
      "type": "http",
      "endpoint": "http://localhost:3000/mcp",
      "timeout_seconds": 30
    }
  },
  "enabled_plugins": {
    "webperf-plugin": true
  }
}
```

**Confusion Point #3: API Key Security**
- **Question:** "Where do I put the actual API key without committing it?"
- **Resolution:** Create `.env` file (gitignored):
  ```bash
  ES_API_KEY=your-actual-elasticsearch-api-key-here
  ```

**Verification:**
```bash
docker-compose up -d
python scripts/verify_connection.py
```

**✅ Success:**
```
Connected to Elasticsearch MCP v1.2.0
Available capabilities: datasets_search, tests_list, source_describe
```

---

### Phase 3: Domain Implementation (5 hours)

#### 3.1 Define Domain Knowledge (90 minutes)

**Sarah's KPIs:**
1. **TTFB** (Time to First Byte) - Server response time
2. **Page Load Time** - Full page render duration
3. **LCP** (Largest Contentful Paint) - Core Web Vital
4. **FCP** (First Contentful Paint) - Initial paint time
5. **API Latency** - Backend API call duration
6. **Error Rate** - Failed request percentage

**Sarah's Dimensions (filters):**
- **region**: us-east, us-west, eu-west, apac, latam
- **page_type**: homepage, product, checkout, search
- **device_type**: desktop, mobile, tablet
- **environment**: production, staging

**Creating Glossaries:**

`src/resources/glossary/webperf_core_metrics.json`:
```json
{
  "glossary_type": "kpis",
  "domain": "webperf",
  "entries": [
    {
      "term": "ttfb",
      "full_name": "Time to First Byte",
      "definition": "Time from navigation start to receiving first byte from server. Critical indicator of backend performance.",
      "unit": "ms",
      "aggregations": ["p50", "p75", "p95", "p99", "mean"],
      "typical_range": "50-300ms for good performance, >500ms indicates backend issues",
      "slo_threshold": "p95 < 500ms",
      "example_queries": [
        "What's the TTFB for checkout?",
        "Show me time to first byte in APAC",
        "Compare server response time between regions",
        "How's backend latency today?",
        "Is TTFB within SLO?"
      ],
      "synonyms": ["time to first byte", "server response time", "backend latency", "TTFB"],
      "related_metrics": ["api_latency", "page_load_time"],
      "business_impact": "Critical for user experience - high TTFB causes page abandonment"
    }
  ]
}
```

`src/resources/glossary/webperf_dimensions.json`:
```json
{
  "glossary_type": "dimensions",
  "domain": "webperf",
  "entries": [
    {
      "term": "region",
      "definition": "Geographic region where measurement was taken",
      "values": ["us-east", "us-west", "eu-west", "apac", "latam"],
      "cardinality": "low (5 values)",
      "example_usage": [
        "in APAC",
        "for us-west region",
        "across all regions",
        "by region",
        "APAC performance"
      ],
      "synonyms": {
        "apac": ["Asia Pacific", "APAC", "asia-pacific", "asia"],
        "us-east": ["US East", "east coast", "us-east-1"],
        "eu-west": ["Europe", "EU", "EMEA"],
        "latam": ["Latin America", "LATAM", "south america"]
      }
    }
  ]
}
```

**AI Assessment:**
```
✅ Required fields: 40/40
✅ Example queries: 25/20 (excellent!)
✅ Synonyms: 15/15
✅ Dimension examples: 15/15
✅ Domain context: 10/10

Score: 105/100 → Ready for Phase 5! 🎉
```

#### 3.2 Map Source Data (30 minutes)

**Sample Elasticsearch Document:**

Sarah exports from Kibana (`sample-es-doc.json`):
```json
{
  "@timestamp": "2024-12-16T10:30:45.123Z",
  "event_type": "pageload",
  "metrics": {
    "ttfb_ms": 245,
    "page_load_time_ms": 2341,
    "lcp_ms": 1876,
    "fcp_ms": 1201
  },
  "labels": {
    "region": "apac",
    "page_type": "checkout",
    "device_type": "mobile",
    "environment": "production"
  },
  "url": "/checkout/payment"
}
```

**Mapping Strategy:**

| Source Field | MetricPoint Field | Notes |
|--------------|-------------------|-------|
| `@timestamp` | `timestamp` | Direct mapping |
| `metrics.ttfb_ms` | `value` | Already in milliseconds |
| `"ttfb"` | `metric_name` | Hardcoded per metric |
| `"ms"` | `unit` | Matches glossary |
| `labels.*` | `dimensions` | All labels become dimensions |

**Confusion Point #4: Unit Consistency**
- **Question:** "My data is in milliseconds, but some Web Vitals docs use seconds. Which should I use?"
- **Resolution:** "Use what matches your source data (ms). Conversion is cheap if needed later. Document in glossary."

#### 3.3 Implement Plugin (120 minutes)

AI generates `src/domain/plugins/webperf_plugin.py` based on scaffold.

**Key Implementation Details:**
- Extracts 6 metrics from single document
- Validates all values with `is_valid_float()`
- Structured logging at extraction start/end/errors
- Graceful handling of missing fields
- Type checks before accessing nested dicts

**Snippet - Metric Extraction:**
```python
def extract(self, json_body, refs, label_values=None, 
            region_filter=None, page_type_filter=None):
    points = []
    
    if not isinstance(json_body, dict):
        logger.warning("Invalid input type", extra={"type": type(json_body).__name__})
        return points
    
    # Extract timestamp
    timestamp = parse_timestamp(json_body.get("@timestamp"))
    if not timestamp:
        logger.warning("Missing timestamp", extra={"doc_keys": list(json_body.keys())})
        return points
    
    # Extract dimensions from labels
    labels = json_body.get("labels", {})
    if not isinstance(labels, dict):
        labels = {}
    
    dimensions = {
        "region": labels.get("region"),
        "page_type": labels.get("page_type"),
        "device_type": labels.get("device_type"),
        "environment": labels.get("environment")
    }
    
    # Apply filters (if specified)
    if region_filter and dimensions.get("region") != region_filter:
        return points  # Filtered out
    
    # Extract metrics
    metrics_data = json_body.get("metrics", {})
    if isinstance(metrics_data, dict):
        ttfb = metrics_data.get("ttfb_ms")
        if is_valid_float(ttfb):
            points.append(MetricPoint(
                timestamp=timestamp,
                metric_name="ttfb",
                value=float(ttfb),
                unit="ms",
                dimensions=dimensions
            ))
    
    return points
```

#### 3.4 Create Test Fixtures (45 minutes)

**Created Files:**
1. `tests/fixtures/webperf/es_pageload_sample.json` - Sarah's real ES doc
2. `tests/fixtures/webperf/expected_metrics.json` - Expected extraction output
3. `tests/test_webperf_plugin.py` - Unit tests

**Test Results:**
```bash
pytest tests/test_webperf_plugin.py -v

tests/test_webperf_plugin.py::test_extract_pageload_metrics PASSED
tests/test_webperf_plugin.py::test_extract_missing_fields PASSED  
tests/test_webperf_plugin.py::test_extract_invalid_types PASSED
tests/test_webperf_plugin.py::test_filter_by_region PASSED
tests/test_webperf_plugin.py::test_filter_by_page_type PASSED

5 passed in 0.34s ✅
```

#### 3.5 Add Custom Filters (90 minutes)

**Filters needed:** region, page_type, device_type, environment

**Confusion Point #5: Filter Alignment**
- **Question:** "Why do I need to update 4 different files for one filter?"
- **AI Explains the flow:**
  ```
  1. normalize.py: Parse "in APAC" → region="apac"
  2. app.py: Pass filter to adapter
  3. elasticsearch.py: Add to ES Query DSL (filter at source)
  4. webperf_plugin.py: Validate results match (safety check)
  ```
- **Resolution:** "Oh! The adapter does heavy lifting, plugin validates. Makes sense!"

**Implementation (following Phase 3.5.3 step-by-step guide):**

**Step 1 - normalize.py:**
```python
region_filter = request_data.get("filters", {}).get("region")
page_type_filter = request_data.get("filters", {}).get("page_type")
```

**Step 2 - app.py:**
```python
async def get_key_metrics(..., region_filter=None, page_type_filter=None):
    datasets = await adapter.datasets_search(
        ...,
        region=region_filter,
        page_type=page_type_filter
    )
```

**Step 3 - elasticsearch.py:**
```python
async def datasets_search(self, ..., region=None, page_type=None):
    must_clauses = []
    
    if region:
        must_clauses.append({"term": {"labels.region.keyword": region}})
    
    if page_type:
        must_clauses.append({"term": {"labels.page_type.keyword": page_type}})
    
    query = {"query": {"bool": {"must": must_clauses}}}
```

**Step 4 - webperf_plugin.py:**
```python
async def extract(self, ..., region_filter=None, page_type_filter=None):
    region = json_body.get("labels", {}).get("region")
    page_type = json_body.get("labels", {}).get("page_type")
    
    if region_filter and region != region_filter:
        return []  # Safety check
    
    if page_type_filter and page_type != page_type_filter:
        return []
```

**Validation:**
```bash
# Test filtered query
LOG_LEVEL=DEBUG python -m src.server.cli run

# In logs, verified:
# 1. "Parsed filter: region=apac" ✅
# 2. "ES Query: {...term: {labels.region: apac}...}" ✅
# 3. "Extracted 45 metrics" ✅
```

---

### Phase 4: Technical Validation (30 minutes)

**Full Test Suite:**
```bash
pytest -v

==================== 47 passed in 12.34s ====================
```

**Start Server:**
```bash
python -m src.server.cli run --host 0.0.0.0 --port 8000

INFO: WebPerf MCP Server listening on http://0.0.0.0:8000
INFO: Connected to Elasticsearch MCP at http://localhost:3000/mcp
INFO: Registered plugin: webperf-plugin
INFO: Loaded glossary resources: webperf_core_metrics, webperf_dimensions
```

**Production Readiness Checklist:**
- ✅ Error handling: Graceful missing field handling
- ✅ Type safety: All dict access validated
- ✅ Logging: Structured with context
- ✅ Performance: Using ES aggregations
- ✅ Testing: Edge cases covered
- ✅ Code quality: Docstrings, type hints complete

**Gate Passed!** Ready for real-world testing.

---

### Phase 5: Query Validation (3 hours)

#### 5.1 Sarah's Real-World Queries

**15 Questions She Asks Daily:**
1. "What's the TTFB for checkout in production?"
2. "Show me page load time in APAC for the last 7 days"
3. "Compare p95 TTFB between regions"
4. "Is our TTFB within SLO today?"
5. "What's the p99 page load time on mobile?"
6. "Show me LCP for homepage"
7. "How's checkout performance compared to last week?"
8. "What's the error rate in staging?"
9. "Show API latency by region"
10. "Is APAC slower than usual?"
11. "What's the desktop vs mobile page load time difference?"
12. "Show me Core Web Vitals for product pages"
13. "Compare this week to last week for homepage"
14. "What's the p95 for all metrics?"
15. "Show me performance in production vs staging"

#### 5.2 Testing with Claude Desktop

**Configuration:**
```json
{
  "mcpServers": {
    "webperf-mcp": {
      "command": "python",
      "args": ["-m", "src.server.cli", "run"],
      "cwd": "/Users/sarah/projects/webperf-mcp",
      "env": {
        "PYTHONPATH": "/Users/sarah/projects/webperf-mcp",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**Test Results:**

**Query #1:** "What's the TTFB for checkout in production?"

**✅ Success:**
```
I'll check the Time to First Byte metrics for checkout pages in production.

Results:
- p50 TTFB: 189ms ✅
- p95 TTFB: 437ms ✅ Within 500ms SLO
- p99 TTFB: 689ms ⚠️ Above threshold

The checkout flow is performing well on average, but the p99 shows 
some users experiencing slower server responses.
```

**Query #10:** "Is APAC slower than usual?"

**⚠️ Partial Success:**
Claude asks: "Slower compared to what? Other regions, or historical APAC performance?"

**Confusion Point #6: Ambiguous Queries**
- **Issue:** Query lacks comparison context
- **Resolution:** Add comparative examples to glossary:
  ```json
  "example_usage": [
    "in APAC",
    "APAC compared to us-west",
    "APAC vs other regions",
    "APAC performance over time"
  ]
  ```

**Retest:** "Is APAC slower than us-east today?"
**✅ Now works!**

#### 5.3 Iteration Results

**After Refinements:**
- ✅ 13/15 queries worked on first try
- ⚠️ 1 query needed rephrasing hint
- ⚠️ 1 query needed glossary enhancement

**Final Tweaks:**
1. Added comparative phrasing examples
2. Enhanced SLO threshold documentation
3. Added business impact context
4. Expanded synonym coverage

**Final Test:** 15/15 queries work! 🎉

---

### Phase 6: Delivery & Documentation (30 minutes)

**Cleanup:**
- ❌ Remove `src/domain/examples/horreum_boot_time.py`
- ❌ Remove `tests/fixtures/boot-time/`
- ❌ Remove template files (scaffold, template JSONs)
- ✅ Update README with WebPerf-specific instructions
- ✅ Create `docs/example_queries.md` with all working queries

**Container Build:**
```bash
podman build -t shopfast/webperf-mcp:v1.0.0 .
```

**Team Rollout:**
- Kubernetes deployment to production
- Shared Claude Desktop config with team
- Demo at team meeting (10 queries shown)
- Documentation wiki page created

**Team Feedback:**
- ✅ "This is way faster than writing Kibana queries!"
- ✅ "Love that it understands our acronyms like TTFB and APAC"
- ✅ "The SLO checking is brilliant - instant status"
- ⚠️ "Can we add browser breakdown?" (added to roadmap)

---

## ⏱️ Time Investment Summary

| Phase | Estimated | Actual | Variance |
|-------|-----------|--------|----------|
| Phase 1: Initialization | 30-60 min | 45 min | On target |
| Phase 2: Connection | 30-60 min | 90 min | +30 min (network debugging) |
| Phase 3: Domain Implementation | 3-6 hours | 5 hours | Within range |
| Phase 4: Validation | 30-60 min | 30 min | Perfect |
| Phase 5: Query Testing | 2-4 hours | 3 hours | On target |
| Phase 6: Delivery | 1-2 hours | 30 min | Faster (good cleanup) |
| **TOTAL** | **8-15 hours** | **10 hours** | **Middle of range** |

**Time Breakdown:**
- **Network debugging:** 60 minutes (30% of Phase 2)
- **Glossary creation:** 180 minutes (36% of Phase 3)
- **Query testing & refinement:** 180 minutes (60% of Phase 5)

**Time Savers:**
- ✅ AI-generated plugin boilerplate: ~90 minutes saved
- ✅ Pre-built test fixture templates: ~45 minutes saved
- ✅ Step-by-step filter walkthrough: ~60 minutes saved (avoided trial-and-error)

---

## 🎯 Key Confusion Points & Resolutions

### 1. Architecture Understanding (Phase 1)
**Confusion:** "What's the difference between Source MCP and Domain MCP?"

**Resolution:** 
- Diagram visualization helped
- Analogy: "Source MCP = database driver, Domain MCP = your business logic"
- Understanding: "I don't write ES queries, the Source MCP does!"

---

### 2. Network/Connection Issues (Phase 2)
**Confusion:** Docker container couldn't reach internal DNS

**Resolution:**
- Switched from stdio to HTTP mode
- Used `network_mode: host` in docker-compose
- Ran Elasticsearch MCP as separate service

**Time Lost:** 30 minutes debugging

**Prevention:** README connection mode decision table helped, but more troubleshooting decision trees would help

---

### 3. API Key Management (Phase 2)
**Confusion:** "Where do I store secrets without committing them?"

**Resolution:**
- Use `.env` file (gitignored)
- Placeholder syntax in config.json: `{{ES_API_KEY}}`
- System substitutes at runtime

**Clarity:** This could be more prominent in Phase 2.1

---

### 4. Unit Consistency (Phase 3.2)
**Confusion:** "Should I use milliseconds or seconds?"

**Resolution:**
- Match source data format (less transformation)
- Document in glossary
- Conversion is cheap if needed later

**Learning:** Don't overthink units - consistency matters more than the specific choice

---

### 5. Filter Implementation Complexity (Phase 3.5)
**Confusion:** "Why update 4 files for one filter?"

**Resolution:** Understanding the data flow:
```
Parse (normalize.py) 
  → Pass (app.py) 
  → Translate (adapter) 
  → Validate (plugin)
```

**Time Saved:** Step-by-step walkthrough in Phase 3.5.3 prevented trial-and-error debugging

---

### 6. Glossary Completeness (Phase 3.1)
**Confusion:** "How many example queries is enough?"

**Resolution:**
- AI assessment scoring (105/100) gave confidence
- Guidelines: minimum 3 examples per KPI, 15-20 total
- Quality targets in Phase 3.1.4 checklist

**Without This:** Would likely have under-specified and struggled in Phase 5

---

### 7. Query Ambiguity (Phase 5)
**Confusion:** "Is APAC slower than usual?" - too vague for LLM

**Resolution:**
- Added comparative phrasing to glossary
- Examples: "APAC vs us-east", "APAC compared to last week"
- Tested variations until natural phrasing worked

**Learning:** LLMs need concrete comparison examples, not just the dimension itself

---

## 💡 Success Factors

### What Worked Extremely Well

1. **Implementation Plan as Single Source of Truth**
   - AI always knew the next step
   - Checkpoints prevented getting lost
   - Phase-by-phase progress tracking

2. **Modular Glossary Structure**
   - Easy to iterate and enhance
   - Could test changes quickly
   - Reusable across multiple plugins (future)

3. **Test-First Approach**
   - Unit tests caught issues before integration
   - Gave confidence plugin worked correctly
   - Faster than debugging in Claude Desktop

4. **Real Sample Data**
   - Using actual Elasticsearch doc made mapping obvious
   - No guessing about field names or structure
   - Test fixtures matched production exactly

5. **Example Domain (PerfScale)**
   - Good reference without being prescriptive
   - Could copy patterns (logging, error handling)
   - Didn't feel forced to follow exactly

### What Could Be Improved

1. **Network Troubleshooting**
   - More decision trees for connection failures
   - Common error messages with solutions
   - Platform-specific guidance (VPN, firewalls)

2. **Glossary Examples**
   - Show "good" vs "excellent" glossary side-by-side
   - More domain examples (not just boot_time)
   - Template for common industries (e-commerce, fintech, etc.)

3. **Performance Guidance**
   - Concrete benchmarks: "10k docs = 10s without aggs, 2s with"
   - When-to-optimize decision tree
   - Cardinality analysis tool (scan data, warn about high-cardinality)

4. **Query Testing Workflow**
   - Pre-built test harness for query validation
   - Regression test suite for queries
   - Query success rate tracking

---

## 📊 ROI Analysis

### Time Investment
- **Setup & Implementation:** 10 hours
- **Learning curve included:** Yes (first MCP project)

### Time Savings (Projected)
- **Before:** 30 minutes/day writing Kibana queries = 2.5 hours/week
- **After:** 5 minutes/day asking Claude questions = 25 minutes/week
- **Savings:** 2 hours/week per engineer

**Team of 5 engineers:**
- Weekly savings: 10 hours
- Monthly savings: 40 hours
- **Break-even:** 1.5 weeks

### Quality Improvements
- Consistent query patterns (no more one-off Kibana queries)
- Self-documenting (glossary serves as team knowledge base)
- Easier onboarding (new engineers ask Claude instead of senior engineers)

### Intangible Benefits
- Engineers enjoy using it ("feels like magic")
- More ad-hoc analysis (lower barrier to asking questions)
- Better incident response (quick performance checks)

---

## 🚀 Next Steps for Sarah

### Immediate (Week 1-2)
- [x] Deploy to production Kubernetes
- [x] Share with team, collect feedback
- [ ] Add monitoring dashboard for MCP server
- [ ] Create Slack bot integration

### Short-term (Month 1-3)
- [ ] Add browser dimension (Chrome, Firefox, Safari)
- [ ] Add synthetic monitoring integration
- [ ] Create alerts for SLO violations
- [ ] Expand to mobile app performance

### Long-term (Quarter 2+)
- [ ] Multi-region deployment
- [ ] Historical comparison features
- [ ] Cost attribution (connect perf to AWS costs)
- [ ] ML-powered anomaly detection

---

## 📚 Key Takeaways for New Users

1. **You Don't Need to Be an MCP Expert**
   - Sarah had never built an MCP server before
   - The template + AI guidance covered the gaps
   - Focus on YOUR domain expertise, not MCP internals

2. **Invest Time in the Glossary**
   - 3 hours creating glossary = 15/15 queries working
   - This is the foundation of query understanding
   - Quality here directly impacts Phase 5 success

3. **Test with Real Data Early**
   - Don't mock data - use actual Elasticsearch documents
   - Catches schema assumptions early
   - Makes mapping obvious

4. **Connection Issues Are Normal**
   - Network debugging is the biggest time sink
   - HTTP mode is more reliable than stdio in corporate environments
   - Budget extra time for this phase

5. **The AI Is Your Pair Programmer**
   - AI handles boilerplate (tests, config, plugin structure)
   - You provide domain expertise (KPIs, glossary, business logic)
   - This division of labor is very effective

6. **Phase 5 Is Make-or-Break**
   - This is where you validate the whole implementation
   - Don't skip query testing - it will catch glossary gaps
   - Iterate until 80%+ success rate

---

## 🎓 Lessons for Template Maintainers

**What This Scenario Revealed:**

1. **Connection troubleshooting needs more depth**
   - Most time lost on network issues
   - Decision trees for common errors would help
   - Platform-specific guides (VPN, firewall, Docker)

2. **Glossary quality is THE critical success factor**
   - Under-specified glossary = Phase 5 failures
   - Assessment scoring helped Sarah immensely
   - More examples of "excellent" glossaries would help

3. **Filter implementation is a pain point**
   - 4-location update is confusing at first
   - Step-by-step walkthrough (Phase 3.5.3) saved the day
   - Could be abstracted/automated further

4. **The example domain (PerfScale) is helpful**
   - Provided patterns to copy
   - Didn't feel forced to follow exactly
   - More domain examples would help (web, fintech, infra)

5. **Testing workflow could be streamlined**
   - Query validation is manual and time-consuming
   - Pre-built test harness would help
   - Automated regression testing for queries

---

## 📖 Related Documentation

- **[IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)** - Detailed phase-by-phase checklist
- **[README.md](../README.md)** - Project overview and setup
- **[EXAMPLE_DOMAIN.md](EXAMPLE_DOMAIN.md)** - PerfScale boot time example breakdown
- **[testing-with-claude-desktop.md](testing-with-claude-desktop.md)** - Phase 5 query testing guide
- **[SOURCE_MCP_QUICKSTART.md](SOURCE_MCP_QUICKSTART.md)** - Understanding the Source MCP contract

---

**Document Version:** 1.0
**Last Updated:** December 2025
**Fictional Scenario - For Educational Purposes**

