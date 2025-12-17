# Domain MCP (Model Context Protocol) Implementation Plan

**Current Status:** [ ] Phase 1: Project Initialization

This document serves as the **master control file** for the AI Agent implementing this Domain MCP server.

## 🤖 AI Driver Instructions

1.  **Read-Execute-Update Loop:** You must follow this process for every task:
    *   **Read** the current phase instructions.
    *   **Execute** the necessary code changes or shell commands.
    *   **Update** this file to mark the task as `[x]` completed.
    *   **Stop** if you reach a "User Confirmation Required" checkpoint.

2.  **Do Not Skip:** Do not skip steps unless explicitly authorized by the user.

3.  **Maintain Context:** If the context window is reset, read this file first to regain your place.

4.  **Keep the User Informed:** Before changing or removing files, tell the user what you are doing and why, and wait for a confirmation from the user.

5.  **Reference Resources:** Keep these files handy for guidance:
    *   **`docs/SOURCE_MCP_QUICKSTART.md`** - 5-minute guide to Source MCP contract (START HERE)
    *   **`docs/EXAMPLE_SCENARIO.md`** - Realistic end-to-end implementation walkthrough (see what the journey looks like)
    *   **`docs/EXAMPLE_DOMAIN.md`** - How the PerfScale example maps to contract concepts
    *   **`src/domain/plugins/plugin_scaffold.py`** - Actionable plugin template with TODOs
    *   **`docs/plugins/plugin-template.py`** - Complete plugin examples with best practices
    *   **`docs/contracts/source-mcp-contract.md`** - Full Source MCP interface specification
    *   **`src/domain/models.py`** - `MetricPoint` and domain model definitions
    *   **`src/domain/examples/`** - Working examples for Elasticsearch and Horreum
    *   **`src/resources/glossary/`** - Example glossary JSON structure
    *   **`schemas/`** - JSON schemas for all Source MCP requests/responses

6.  **Deep Dive Guides:** This plan references supporting documentation for complex topics:
    *   **Phase 3.4 fixtures:** `tests/fixtures/template/README.md` has 6 detailed test scenarios
    *   **Phase 3.5 filters:** Section 3.5.3 below has step-by-step code examples for all 4 locations
    *   **Phase 5 testing:** `docs/testing-with-claude-desktop.md` has complete Claude Desktop setup
    *   **Phase 5 debugging:** Section 5.3.3 below has systematic query debugging decision tree
    *   Don't read all supporting docs upfront - references are provided when needed in each phase.

---

## 📋 Implementation Phases Overview

This implementation follows a 6-phase process:

**Phase 1: Project Initialization** (30-60 minutes)
- Define project identity and domain
- Prune unused adapters
- Clean up documentation

**Phase 2: Configuration & Connection** (30-60 minutes)
- Configure Source MCP connection
- Verify connectivity
- Ensure data source is accessible

**Phase 3: Domain Implementation** (3-6 hours)
- Define KPIs and dimensions
- Create plugin extraction logic
- Build test fixtures
- Add custom filters if needed

**Phase 4: Technical Validation** (30-60 minutes)
- Run test suite
- Verify server starts correctly
- Smoke test basic functionality

**Phase 5: Fine-Tuning & Query Validation** (2-4 hours) ⭐ **CRITICAL**
- Test with real-world natural language queries
- Validate results meet expectations
- Refine glossary based on query understanding
- Document working queries
- **Gate:** 80%+ query success rate required

**Phase 6: Delivery & Documentation** (1-2 hours)
- Final cleanup and review
- Deployment preparation
- Team onboarding
- Celebrate completion! 🎉

**Total Estimated Time:** 8-15 hours (with AI assistance)

---

## ✈️ Pre-Flight Checklist

Before starting Phase 1, ensure you have:

**Data Source Access:**
- [ ] Access to your data source (Elasticsearch cluster, Horreum instance, database, etc.)
- [ ] Credentials (API key, username/password, or token)
- [ ] Network connectivity verified (can you reach the data source from your machine?)

**Data Understanding:**
- [ ] 2-3 sample documents/records exported (save as JSON for reference)
- [ ] Understanding of your data schema:
  - [ ] What field contains the timestamp?
  - [ ] What fields contain metric values?
  - [ ] What fields should be dimensions (filters)?
- [ ] List of 3-5 Key Performance Indicators (KPIs) you want to track

**Environment Setup:**
- [ ] Python 3.10+ installed
- [ ] Container Runtime installed: Docker or Podman (if using stdio mode for Elasticsearch)
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] Git configured (for version control)

**Connection Mode Decision (for Elasticsearch users):**
- [ ] Reviewed README "Connection Mode Decision Guide"
- [ ] Decided: stdio mode or HTTP mode?
- [ ] If stdio: Verified Docker can reach your ES cluster
- [ ] If HTTP: Plan to run ES MCP as separate service

**Performance Considerations:**
- [ ] Estimated document count in your data source
- [ ] If >100k documents: Planned aggregation strategy (source-side vs domain-side)
- [ ] Identified high-cardinality fields to avoid as dimensions

**Optional but Recommended:**
- [ ] Reviewed `docs/SOURCE_MCP_QUICKSTART.md` (5-minute read)
- [ ] Looked at example plugin: `src/domain/examples/elasticsearch_logs.py` or `horreum_boot_time.py`
- [ ] Familiarized with `MetricPoint` structure in `src/domain/models.py`

---

## Phase 1: Project Initialization & Scoping

**Goal:** Define the identity of this Domain MCP and select the Source MCP it will connect to.

- [ ] **1.1. Confirm Project Identity** (User Input Required)
    *   Project Name: `[Enter Name Here]` (e.g., `payment-search-mcp`)
    *   Domain: `[Enter Domain Here]` (e.g., "Payment Transaction Search")
    *   Target Source MCP: `[Horreum | Elasticsearch | Custom]`

- [ ] **1.2. Configure Enabled Adapters**
    *   Instead of removing adapter files, you will enable or disable adapters by modifying the `config.json` file. Only the adapters defined in the `sources` array within `config.json` will be initialized.
    *   Initially, you might want to keep both `src/adapters/elasticsearch.py` and `src/adapters/horreum.py` for reference. You can then configure which ones are active in `config.json`.

- [ ] **1.3. Clean Up Documentation and Example References**
    *   Update `README.md` with the new Project Name.
    *   Remove or adapt PerfScale-specific references (see `docs/EXAMPLE_DOMAIN.md` cleanup checklist):
        - `src/__version__.py` - Update description
        - Documentation files already have template notes added
        - Consider keeping example files (`src/domain/examples/`) temporarily as reference, remove later
    *   Update all "RHIVOS PerfScale" references in remaining docs to your project name.

**Checkpoint:** Request user confirmation that the project structure is correct.

---

## Phase 2: Configuration & Connection

**Goal:** Connect the Domain MCP to the Source MCP.

- [ ] **2.1. Configure Source MCPs**
    *   Update `config.json` to define your Source MCPs. The `AppConfig` model now supports multiple sources, each with its own `id`, `type`, and connection details.
    *   **Example `config.json` structure:**
        ```json
        {
          "name": "My Domain MCP",
          "description": "...",
          "sources": [
            {
              "id": "my-horreum-source",
              "type": "horreum",
              "endpoint": "https://horreum.example.com",
              "api_key": "super-secret-horreum-token",
              "timeout_seconds": 30
            },
            {
              "id": "my-es-source",
              "type": "elasticsearch",
              "endpoint": "uvx mcp-server-elasticsearch",
              "stdio_args": ["--es-url", "http://localhost:9200"],
              "timeout_seconds": 60
            }
          ],
          "plugins": [...]
        }
        ```
    *   **Key fields per source:**
        - `id`: A unique identifier for this source (e.g., `my-horreum-source`, `perfscale-es`).
        - `type`: `horreum` or `elasticsearch`.
        - `endpoint`: For Horreum, the base URL; for Elasticsearch, the command to run the Source MCP (e.g., `uvx mcp-server-elasticsearch`).
        - `api_key` (Horreum only): The API key for authentication.
        - `stdio_args` (Elasticsearch only): A list of arguments for the Source MCP command.
        - `timeout_seconds`: Optional timeout for connection (defaults to 30).
    *   **💡 Tip for Podman Users:** If using Podman, set the `endpoint` to your podman run command.
        - Example: `"endpoint": "podman run -i --rm -e ELASTICSEARCH_URL=... mcp-server-elasticsearch"`
        - Ensure `-i` (interactive) is used so stdin/stdout are connected.

- [ ] **2.2. Verify All Source Connections**
    *   Run the verification script to ensure all configured adapters can connect to their respective Source MCPs:
        ```bash
        python scripts/verify_connection.py
        ```
    *   Expected output: Source MCP name, version, capabilities for *each* configured source.
    *   If any connection fails, check `config.json` for that specific source and ensure the Source MCP is available.

**Checkpoint:** Confirm successful connection to the Source MCP.

---

## Phase 3: Domain Implementation

**Goal:** Implement the logic that translates Source Data into Domain Metrics.

### 3.1. Define Your Domain Knowledge

- [ ] **3.1.1. Identify Key Performance Indicators (KPIs)**
    *   List 3-5 metrics that matter in your domain (e.g., "boot_time_seconds", "error_rate", "throughput").
    *   For each KPI, note:
        - **Name** (snake_case)
        - **Description** (natural language)
        - **Unit** (e.g., "seconds", "count", "bytes/sec")
        - **Aggregation** (e.g., "mean", "p95", "sum")

- [ ] **3.1.2. Create Glossary Entries**
    *   **Start from templates:**
        - Copy `src/resources/glossary/template_kpis.json` to `my_domain_kpis.json`
        - Copy `src/resources/glossary/template_dimensions.json` to `my_domain_dimensions.json`
    *   Replace TODOs with your domain terminology
    *   Each KPI entry should have:
        - `term`: The KPI name (snake_case)
        - `definition`: Human-readable explanation
        - `unit`: Measurement unit
        - `aggregations`: Supported aggregations (mean, p95, etc.)
        - `example_queries`: Natural language examples
    *   Reference: `src/resources/glossary/boot_time_kpis.json` for working examples

- [ ] **3.1.3. Document Domain-Specific Dimensions**
    *   Identify filters/groupings users will ask for (e.g., "by region", "by kernel version").
    *   Add them to glossary entries as `dimensions`.

- [ ] **3.1.4. Glossary Completeness Assessment**

    Use this checklist to ensure your glossary is complete enough for Phase 5 query validation.

    **Minimum Requirements Per KPI Entry:**
    - [ ] Term defined (snake_case, matches plugin metric_name exactly)
    - [ ] Human-readable name and definition (1-2 sentences explaining what it measures)
    - [ ] Unit specified (use short form: `ms`, `s`, `bytes`, `count`, `%`)
    - [ ] **Minimum 3 example queries** showing different phrasings
    - [ ] **Minimum 2 synonyms** (especially critical for acronyms)
    - [ ] Preferred aggregations listed (p50, p75, p95, p99, mean, sum, etc.)
    - [ ] Typical value range documented (helps LLM validate results)

    **Example KPI Entry (Web Performance):**
    ```json
    {
      "term": "ttfb",
      "full_name": "Time to First Byte",
      "definition": "Time from navigation start to receiving first byte from server",
      "unit": "ms",
      "aggregations": ["p50", "p75", "p95", "p99", "mean"],
      "typical_range": "50-300ms for good performance, >500ms indicates issues",
      "example_queries": [
        "What's the TTFB for checkout?",
        "Show me time to first byte in APAC",
        "Compare server response time between regions",
        "How's the backend latency today?"
      ],
      "synonyms": ["time to first byte", "server response time", "backend latency", "TTFB"]
    }
    ```

    **Minimum Requirements Per Dimension Entry:**
    - [ ] Term defined (snake_case, matches dimension key in MetricPoint)
    - [ ] Description of what it represents
    - [ ] **List of valid values** (if < 50 unique values)
    - [ ] **Minimum 3 usage examples** showing how users would reference it
    - [ ] Common synonyms (e.g., "prod" = "production", "EMEA" = "Europe/Middle East/Africa")

    **Example Dimension Entry:**
    ```json
    {
      "term": "region",
      "definition": "Geographic region where measurement was taken",
      "values": ["us-east", "us-west", "eu-west", "eu-central", "apac", "emea"],
      "example_usage": [
        "in APAC",
        "for us-west region",
        "across all regions",
        "by region"
      ],
      "synonyms": {
        "apac": ["Asia Pacific", "APAC", "asia-pacific"],
        "emea": ["Europe", "EMEA", "EU"],
        "us-east": ["US East", "us-east-1", "east coast"]
      }
    }
    ```

    **Quality Targets:**

    **Coverage (100% Required):**
    - [ ] All plugin KPIs have glossary entries (no exceptions)
    - [ ] All plugin dimensions have glossary entries (no exceptions)
    - [ ] All acronyms are expanded with full names
    - [ ] Top 5 most-used KPIs have 5+ example queries each

    **Example Query Count:**
    - [ ] **Total example queries across all KPIs: Minimum 15-20**
    - [ ] At least 3 different time range phrasings ("today", "last week", "past 30 days")
    - [ ] At least 3 different comparison phrasings ("between X and Y", "compared to", "vs")
    - [ ] At least 2 multi-filter queries ("Show X in Y for Z")

    **Domain Context Documentation:**
    - [ ] Normal value ranges specified ("Typical: 100-500ms")
    - [ ] Abnormal patterns noted ("Values >2000ms indicate server issues")
    - [ ] Business context provided ("Critical for checkout conversion rate")
    - [ ] Related KPIs cross-referenced ("Often analyzed with error_rate")

    ---

    **Assessment Scoring (AI Agent Use This):**

    When reviewing a user's glossary, score it on these criteria:

    **Score 0-100:**
    - **Required fields present:** 40 points (all or nothing - must have term, definition, unit, aggregations)
    - **Example query count:** 20 points (1 point per unique example query, cap at 20)
    - **Synonym coverage:** 15 points (3 points per KPI with 2+ synonyms, cap at 15)
    - **Dimension examples:** 15 points (3 points per dimension with 3+ usage examples, cap at 15)
    - **Domain context:** 10 points (value ranges, business impact, relationships documented)

    **Minimum score to proceed to Phase 5: 70/100**

    **If below 70, guide user to add:**
    1. Identify weakest area (category with least points)
    2. Provide specific examples of what to add
    3. Re-evaluate after improvements

    **Example Assessment:**
    ```
    ✅ Required fields: 40/40 (all KPIs have term, definition, unit, aggregations)
    ⚠️  Example queries: 12/20 (only 12 examples total - need 8 more for better coverage)
    ✅ Synonyms: 15/15 (all 5 acronyms have 2+ alternatives)
    ⚠️  Dimension examples: 9/15 (only 3 dimensions have 3+ examples - need 6 more)
    ✅ Domain context: 10/10 (value ranges and business context well-documented)

    Total: 86/100 → ✅ Ready for Phase 5
    ```

    ```
    ⚠️  Required fields: 40/40 (present but some units inconsistent)
    ❌ Example queries: 6/20 (only 6 examples - need 14 more)
    ⚠️  Synonyms: 6/15 (only 2 KPIs have synonyms - need 3 more)
    ❌ Dimension examples: 3/15 (only 1 dimension has examples - need 12 more)
    ⚠️  Domain context: 4/10 (minimal context provided)

    Total: 59/100 → ❌ Not ready - focus on example queries and dimension usage first
    ```

### 3.2. Map Source Data to Domain Model

- [ ] **3.2.1. Inspect Source Data Shape**
    *   Fetch a sample raw response from your Source MCP.
    *   Identify fields that map to:
        - **Timestamp** (when the measurement occurred)
        - **Metric value** (the KPI measurement)
        - **Dimensions** (labels/tags like `{"region": "us-west"}`)
        - **Unit** (if present in source data)

- [ ] **3.2.2. Map Fields to MetricPoint**
    *   Open `src/domain/models.py` to see the `MetricPoint` structure.
    *   Plan your mapping:
        - `timestamp` ← source field (e.g., `doc["@timestamp"]`)
        - `metric_name` ← your KPI name (e.g., `"boot_time_seconds"`)
        - `value` ← source field (e.g., `doc["duration_ms"] / 1000`)
        - `unit` ← hardcoded or from source
        - `dimensions` ← dict of labels (e.g., `{"arch": doc["architecture"]}`)

### 3.3. Implement Plugin

- [ ] **3.3.1. Create Plugin File**
    *   **Option A (Recommended for new domains):** Copy `src/domain/plugins/plugin_scaffold.py` to `src/domain/plugins/my_plugin.py` and fill in the TODOs.
    *   **Option B (Adapt from example):** Copy a relevant example from `src/domain/examples/` to `src/domain/plugins/my_plugin.py` and modify.
    *   Rename class and update docstring to match your domain.
    *   Reference: `docs/plugins/plugin-template.py` for complete examples and best practices.

- [ ] **3.3.2. Implement `extract()` Method**
    *   Parse the `json_body` parameter (raw source data).
    *   For each measurement in the source data:
        - Extract timestamp, value, dimensions using your mapping from 3.2.2
        - Create a `MetricPoint` instance
        - Apply any domain-specific transformations (unit conversions, filtering)
    *   Return `List[MetricPoint]`.

- [ ] **3.3.3. Handle Edge Cases**
    *   Missing fields: decide whether to skip or use defaults
    *   Unit conversions: ensure consistency (e.g., ms → seconds)
    *   Invalid data: log warnings, don't crash

- [ ] **3.3.4. Register Plugin**
    *   Update `src/domain/plugins/__init__.py`:
        - Import your plugin class
        - Add it to the registry/export list
    *   Ensure plugin name matches your domain (used in config/routing).

- [ ] **3.3.5. Add Production Logging (Recommended)**
    
    Structured logging is critical for debugging production issues. Add logging at key points in your plugin:
    
    **Why Structured Logging?**
    - Searchable: Query logs by event type, field values, error codes
    - Contextual: Each log includes relevant data (IDs, counts, values)
    - Analyzable: Export to log aggregators (Elasticsearch, Splunk, CloudWatch)
    - Debuggable: Understand what happened without reproducing locally
    
    **Pattern 1: Log Extraction Start**
    
    Add at the beginning of your `extract()` method:
    ```python
    logger.info(
        "%s.extract.start",
        self.id,
        extra={
            "document_keys": list(json_body.keys()) if isinstance(json_body, dict) else None,
            "ref_keys": list(refs.keys()) if refs else [],
            "has_label_values": bool(label_values),
            "filters_applied": {
                "region": region_filter if 'region_filter' in locals() else None,
                "os": os_filter if 'os_filter' in locals() else None,
            },
            "document_size_bytes": len(str(json_body)) if json_body else 0,
        }
    )
    ```
    
    **What this tells you:**
    - Which keys are in the source document (detect schema changes)
    - What references are available (test_id, run_id, etc.)
    - Whether optimizations are being used (label_values)
    - What filters are active (helps debug filter issues)
    - Document size (helps identify large documents causing slowness)
    
    **Pattern 2: Log Extraction Results**
    
    Add at the end of your `extract()` method (before return):
    ```python
    logger.info(
        "%s.extract.complete",
        self.id,
        extra={
            "metrics_extracted": len(points),
            "metric_ids": [p.metric_name for p in points[:5]],  # First 5
            "metric_values": [p.value for p in points[:3]],  # First 3 values
            "dimensions": points[0].dimensions if points else None,
            "timestamp": points[0].timestamp.isoformat() if points else None,
            "processing_time_ms": (time.time() - start_time) * 1000,  # Add start_time at method entry
        }
    )
    ```
    
    **What this tells you:**
    - How many metrics were extracted (0 = problem)
    - Which metrics were created (verify expected metrics)
    - Sample values (sanity check - are they reasonable?)
    - What dimensions were extracted (verify dimension extraction)
    - Performance (identify slow extractions)
    
    **Pattern 3: Log Skipped/Filtered Data**
    
    Add when filtering out documents:
    ```python
    if region_filter and region != region_filter:
        logger.debug(
            "%s.extract.filtered_out",
            self.id,
            extra={
                "reason": "region_mismatch",
                "filter_expected": region_filter,
                "dimension_found": region,
                "document_id": refs.get("id"),
            }
        )
        return []
    
    # Or for missing required fields:
    if not timestamp:
        logger.warning(
            "%s.extract.missing_required_field",
            self.id,
            extra={
                "field": "timestamp",
                "document_keys": list(json_body.keys())[:10],
                "document_id": refs.get("id"),
            }
        )
        return []
    ```
    
    **What this tells you:**
    - Why documents were skipped (helps tune filters)
    - Which documents are problematic (can investigate specific IDs)
    - Whether your data has expected structure
    
    **Pattern 4: Log Validation Failures**
    
    Add when data validation fails:
    ```python
    raw_value = json_body.get("latency_ms")
    if not is_valid_float(raw_value):
        logger.warning(
            "%s.extract.invalid_value",
            self.id,
            extra={
                "field": "latency_ms",
                "value": str(raw_value)[:100],  # Truncate long values
                "value_type": type(raw_value).__name__,
                "expected_type": "float",
                "document_id": refs.get("id"),
            }
        )
        return []
    ```
    
    **What this tells you:**
    - Which fields have invalid data
    - What the invalid values are (helps fix data pipeline)
    - How common validation failures are
    
    **Pattern 5: Log Errors with Context**
    
    In your exception handler:
    ```python
    except Exception as e:
        logger.error(
            "%s.extract.error",
            self.id,
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "document_keys": list(json_body.keys()) if isinstance(json_body, dict) else None,
                "document_id": refs.get("id"),
                "partial_results": len(points),
                "traceback": traceback.format_exc()[:500],  # First 500 chars
            },
            exc_info=True  # Include full stack trace
        )
    ```
    
    **What this tells you:**
    - What type of error occurred
    - Which document caused it
    - Whether you got partial results
    - Full context for debugging
    
    **Querying Structured Logs**
    
    Once logs are in a log aggregator, you can query them:
    
    ```
    # Find all validation failures in the last hour
    event: "*.extract.invalid_value" AND timestamp:[now-1h TO now]
    
    # Find documents that were filtered out by region
    event: "*.extract.filtered_out" AND reason:"region_mismatch"
    
    # Find slow extractions (>1 second)
    event: "*.extract.complete" AND processing_time_ms:>1000
    
    # Find errors for specific document
    event: "*.extract.error" AND document_id:"abc123"
    
    # Count metrics extracted per plugin
    SELECT count(*), plugin FROM logs 
    WHERE event LIKE '%.extract.complete' 
    GROUP BY plugin
    ```
    
    **Log Levels Guide**
    
    | Level | When to Use | Example |
    |-------|-------------|---------|
    | `DEBUG` | Detailed flow, filtering decisions | "Skipped due to filter mismatch" |
    | `INFO` | Normal operations, metrics extracted | "Extracted 5 metrics successfully" |
    | `WARNING` | Recoverable issues, missing optional data | "Missing optional field, using default" |
    | `ERROR` | Errors that prevent extraction | "Invalid JSON structure, skipping document" |
    
    **Performance Considerations**
    
    - Use `DEBUG` level for verbose logs (filter decisions, field extraction)
    - Production should run at `INFO` level (start/complete/errors only)
    - Avoid logging large objects (truncate to first 100-500 chars)
    - Don't log in tight loops (aggregate first, then log summary)
    
    **Security Notes**
    
    - **Never log sensitive data:** PII, passwords, API keys, tokens
    - **Redact before logging:** Email → `e***@domain.com`, phone → `***-***-1234`
    - **Use document IDs, not contents:** Reference IDs you can look up separately
    
    **Testing Your Logging**
    
    ```bash
    # Run with debug logging to see all logs
    LOG_LEVEL=DEBUG pytest tests/test_your_plugin.py -v -s
    
    # Check log output includes structured data
    # Look for: "extra={...}" in log messages
    
    # Verify no sensitive data in logs
    # Search for patterns: email addresses, phone numbers, tokens
    ```
    
    **Example: Complete Plugin with Logging**
    
    See `src/domain/examples/` for working examples with production logging patterns.

### 3.4. Create Validation Fixtures

- [ ] **3.4.1. Add Sample Source Data**
    *   **Start from template:** Copy `tests/fixtures/template/source_response_sample.json` to `tests/fixtures/my_domain/`
    *   Replace TODOs with a real response from your Source MCP (use `datasets_search()`)
    *   Redact sensitive data if needed
    *   Rename to match your domain (e.g., `payment_logs_sample.json`)

- [ ] **3.4.2. Add Expected Extraction Output**
    *   **Start from template:** Copy `tests/fixtures/template/expected_metrics.json` to `tests/fixtures/my_domain/`
    *   Manually write what your plugin should output for the sample input
    *   Include at least 2-3 `MetricPoint` examples
    *   This becomes your test assertion target

- [ ] **3.4.3. Create Plugin Unit Test**
    *   **Start from template:** Copy `tests/test_template_plugin.py` to `tests/test_my_domain_plugin.py`
    *   Uncomment and update test to use your fixtures
    *   Run: `pytest tests/test_my_domain_plugin.py -v`

**📖 Need more detail on test fixtures?** See `tests/fixtures/template/README.md` for:
- 6 specific test scenarios with examples
- Minimum coverage requirements
- AI Agent verification checklist

### 3.5. Update Adapter Contract Mappings (if needed)

- [ ] **3.5.1. Review Adapter Methods**
    *   Check your adapter (`src/adapters/elasticsearch.py` or `horreum.py`)
    *   Verify `tests_list()` returns relevant sources (e.g., index patterns, test IDs)
    *   Verify `datasets_search()` correctly filters by time range and other filters

- [ ] **3.5.2. Add Custom Filters (optional)**
    *   If your domain needs special filters (e.g., `region`, `version`):
        1.  Add to `src/server/normalize.py` (parse from user query)
        2.  Add to `src/server/app.py` (pass to adapter)
        3.  Add to your adapter (translate to source query, e.g., ES Query DSL)
        4.  Add to plugin (filter results if source filtering is incomplete)
    *   See Developer Notes below for filter alignment checklist.
    *   **⚠️ Adding a filter? Don't skip section 3.5.3 below** - it has step-by-step code examples for all 4 locations.

- [ ] **3.5.3. Adding a Custom Filter: Step-by-Step Walkthrough**

    When adding a new filter (e.g., `region`), guide the user through these 4 locations with concrete examples:

    **Step 1: Update normalize.py (Parse the filter from natural language)**

    **Location:** `src/server/normalize.py`

    **Find this function:** `def normalize_request(...)`

    **Add parameter extraction:**
    ```python
    # Extract region filter if present
    region_filter = request_data.get("filters", {}).get("region")
    # Or from natural language hints in the query text
    ```

    **AI Agent Instruction:** 
    - Ask user: "What natural language phrases indicate this filter?" 
    - Examples: "in APAC", "for us-west region", "across all regions"
    - Update parsing logic to extract these

    ---

    **Step 2: Update app.py (Pass filter to adapter)**

    **Location:** `src/server/app.py` (or `http.py` for HTTP mode)

    **Find the function:** `async def get_key_metrics(...)`

    **Add to function signature and adapter call:**
    ```python
    async def get_key_metrics(
        ...,
        source_id: str, # Already present, but including for context
        region_filter: Optional[str] = None,  # Add this
    ):
        # Pass to adapter
        datasets = await adapter.datasets_search(
            source_id=source_id, # Must pass source_id to the adapter
            ...,
            region=region_filter,  # Add this
        )
    ```

    ---

    **Step 3: Update adapter (Translate to source query)**

    **Location:** `src/adapters/elasticsearch.py` (or your adapter)

    **Find the function:** `async def datasets_search(...)`

    **Add to function signature:**
    ```python
    async def datasets_search(
        self,
        ...,
        region: Optional[str] = None,  # Add this
    ):
    ```

    **Add to query building (Elasticsearch example):**
    ```python
    # Build the must clauses
    must_clauses = []

    if region:
        must_clauses.append({
            "term": {"user.region.keyword": region}
        })
        
    query = {
        "query": {
            "bool": {
                "must": must_clauses,
                # ... rest of query
            }
        }
    }
    ```

    **AI Agent Instruction - Source-Specific Translation:**
    - **For Elasticsearch:** Use `{"term": {"field.keyword": value}}` for exact match on string fields
    - **For SQL databases:** Add to WHERE clause: `WHERE region = ?` with parameterized query
    - **For Horreum:** Add to labels filter in request body
    - **For time-series DBs:** Add as tag filter according to DB query language

    ---

    **Step 4: Update plugin (Post-filter validation)**

    **Location:** `src/domain/plugins/your_plugin.py`

    **Find the function:** `async def extract(...)`

    **Add to function signature:**
    ```python
    async def extract(
        self,
        json_body: object,
        refs: Dict[str, str],
        label_values: Optional[List[Any]] = None,
        region_filter: Optional[str] = None,  # Add this
    ) -> List[MetricPoint]:
    ```

    **Add filtering logic:**
    ```python
    # Extract dimension value from source data
    region = json_body.get("user", {}).get("region")
    # Or: region = json_body.get("labels", {}).get("region")
    # Or: region = json_body.get("region")  # depends on your source structure

    # Apply filter if specified (as safety check)
    if region_filter and region != region_filter:
        logger.debug(f"Skipping document: region {region} != filter {region_filter}")
        return []  # Skip this document
        
    # Add to dimension extraction
    dimensions = {
        "region": region,
        # ... other dimensions
    }
    ```

    ---

    **Validation Checklist (AI Agent: Guide user through this)**

    After adding the filter, verify it works correctly:

    - [ ] **Test with filter:** Query "show me [metric] in [filter-value]" returns only filtered results
    - [ ] **Test without filter:** Query "show me [metric]" (no filter) returns all results
    - [ ] **Check logs:** Server logs show filter was parsed and passed through chain
    - [ ] **Verify adapter query:** For ES, check Query DSL includes filter term
    - [ ] **Validate results:** All returned documents match the filter value
    - [ ] **Test invalid filter:** Query with non-existent filter value returns empty results (not error)

    **Quick validation command:**
    ```bash
    # Enable debug logging
    export LOG_LEVEL=DEBUG
    
    # Start server and watch logs
    python -m src.server.cli run
    
    # In logs, look for:
    # 1. "Parsed filter: region=apac"
    # 2. "ES Query: {...term: {region: apac}...}"
    # 3. "Extracted N metrics"
    ```

### 3.6. Backend-Specific Optimizations (Optional but Recommended)

**Goal:** Leverage your backend's strengths for better performance at scale.

- [ ] **3.6.1. Identify Your Backend's Optimization Features**

    Different backends offer different optimization capabilities. Use what your backend provides:

    **For Horreum Users:**
    
    ✅ **Label Values** - Horreum's pre-computed metrics feature
    - **What it is:** Horreum pre-computes and stores metrics server-side
    - **Performance:** 10-100x faster than parsing raw datasets
    - **Benefits:** 
        - Server-side filtering and aggregation
        - Smaller data transfer (metrics only, not full JSON)
        - No client-side parsing overhead
    - **Implementation:**
        1. Add `label_values` parameter to plugin `extract()` method
        2. Try extracting from label_values first
        3. Fallback to dataset parsing if labels incomplete
    - **Example pattern:**
        ```python
        async def extract(self, json_body, refs, label_values=None, ...):
            # Try label values first (fast path)
            if label_values:
                points = self._extract_from_label_values(label_values)
                if points:
                    return points  # Success!
            
            # Fallback to dataset parsing (slower)
            return self._extract_from_dataset(json_body)
        ```
    - **Reference:** See `rhivos-perfscale-mcp` `boot_time.py` for complete implementation
    
    **For Elasticsearch Users:**
    
    ✅ **Aggregations API** - Let ES compute statistics server-side
    - **What it is:** Elasticsearch's built-in aggregation engine
    - **Performance:** 10-100x faster for large datasets (>10k documents)
    - **Benefits:**
        - Compute percentiles, histograms, stats server-side
        - Fetch results only, not raw documents
        - Reduced memory usage and data transfer
    - **Implementation:**
        1. Add aggregation logic to adapter's `datasets_search()`
        2. Request ES aggregations instead of raw documents
        3. Extract results from aggregation response
    - **Example:**
        ```python
        # In your adapter's datasets_search()
        query = {
            "size": 0,  # Don't fetch documents
            "aggs": {
                "latency_p95": {
                    "percentiles": {
                        "field": "latency_ms",
                        "percents": [50, 75, 95, 99]
                    }
                },
                "latency_avg": {
                    "avg": {"field": "latency_ms"}
                }
            }
        }
        ```
    - **When to use:** Queries with >10,000 documents, percentile calculations
    
    **For SQL Databases:**
    
    ✅ **Aggregate Functions** - Use SQL's GROUP BY and aggregate functions
    - **What it is:** `AVG()`, `PERCENTILE_CONT()`, `COUNT()`, `SUM()` in SQL
    - **Benefits:**
        - Database optimized for aggregations
        - Leverage indexes and query planning
        - Return summary data only
    - **Example:**
        ```sql
        SELECT 
            region,
            AVG(latency_ms) as avg_latency,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency
        FROM metrics
        WHERE timestamp >= ? AND timestamp <= ?
        GROUP BY region
        ```
    
    **For Time-Series Databases (Prometheus, InfluxDB, TimescaleDB):**
    
    ✅ **Built-in Time-Series Functions**
    - **Prometheus:** `rate()`, `quantile()`, `histogram_quantile()`
    - **InfluxDB:** `percentile()`, `mean()`, `derivative()`
    - **TimescaleDB:** Continuous aggregates, time_bucket()
    - **Benefits:** Optimized for time-series analysis
    - **Implementation:** Use backend's native query language in adapter

- [ ] **3.6.2. When to Use Server-Side vs Client-Side Aggregation**

    **Decision Matrix:**

    | Your Situation | Recommendation | Why |
    |----------------|----------------|-----|
    | Dataset < 1,000 documents | **Client-side** (domain-side) | Fast enough, simpler code |
    | Dataset > 10,000 documents | **Server-side** (backend aggregation) | Significantly faster, less memory |
    | Backend supports aggregations | **Server-side preferred** | Leverage backend optimization |
    | Backend doesn't support aggregations | **Client-side required** | Only option available |
    | Custom/complex aggregations | **Client-side** | More flexibility in Python |
    | Multiple data sources | **Client-side** | Combine data after fetching |
    | Prototyping/development | **Client-side** | Easier to iterate and debug |
    | Production at scale | **Server-side** | Better performance and resource usage |

    **Use server-side aggregation when:**
    - [ ] Dataset has >10,000 data points
    - [ ] Computing percentiles, histograms, or complex statistics
    - [ ] Your backend explicitly supports aggregations
    - [ ] Query performance is too slow (>10 seconds)
    - [ ] Memory usage is a concern
    
    **Use client-side aggregation when:**
    - [ ] Dataset has <1,000 data points
    - [ ] Need custom aggregations not supported by backend
    - [ ] Combining data from multiple heterogeneous sources
    - [ ] Prototyping or iterating quickly
    - [ ] Backend doesn't support aggregations
    
    **Default recommendation:** Start with client-side (simpler), optimize to server-side when performance becomes an issue.

- [ ] **3.6.3. Document Your Optimization Strategy**
    
    Add a section to your plugin docstring explaining your approach:
    
    ```python
    """
    My Domain Plugin
    
    Extracts payment transaction metrics from Elasticsearch.
    
    Data Access Strategy:
    - Uses Elasticsearch aggregations for percentiles (>10k documents)
    - Falls back to client-side statistics for small datasets (<1k documents)
    - Caches aggregation results for 5 minutes to reduce query load
    
    Performance Characteristics:
    - Small datasets (<1k): ~1-2 seconds
    - Medium datasets (1k-10k): ~3-5 seconds
    - Large datasets (>10k): ~5-10 seconds with aggregations
    """
    ```

- [ ] **3.6.4. Test Both Paths (if implementing server-side optimization)**
    
    If you implement backend-specific optimizations:
    
    - [ ] Test with small dataset (verify client-side path works)
    - [ ] Test with large dataset (verify server-side path works)
    - [ ] Test fallback logic (what happens if aggregation fails?)
    - [ ] Measure performance improvement (before/after)
    - [ ] Document trade-offs in your README

    **Example test strategy:**
    ```python
    # Test client-side path
    def test_small_dataset_extraction():
        # With 100 documents, should use client-side stats
        pass
    
    # Test server-side path
    def test_large_dataset_aggregation():
        # With 50k documents, should use ES aggregations
        pass
    
    # Test fallback
    def test_aggregation_fallback():
        # If ES aggregation fails, should fall back to client-side
        pass
    ```

**⚠️ Important Notes:**

- **Don't over-optimize early:** Start simple (client-side), optimize when you have evidence of performance issues
- **Backend-specific code lives in adapters:** Keep plugins backend-agnostic when possible
- **Document what you chose:** Future maintainers need to understand your decisions
- **Test both paths:** Optimizations can introduce bugs - test thoroughly

---

## Phase 4: Technical Validation

**Goal:** Ensure the implementation is technically correct.

- [ ] **4.1. Run Tests**
    *   Update `tests/` to match your new plugin and adapter.
    *   Run `pytest`.
    *   All tests should pass.

- [ ] **4.2. Integration Smoke Test**
    *   Start the server: `python -m src.server.cli run --host 0.0.0.0 --port 8000`
    *   Verify server starts without errors
    *   Check health endpoint is responding

- [ ] **4.3. Production Readiness Checklist**
    
    Before proceeding to Phase 5 query validation, verify your implementation meets production quality standards:
    
    **Error Handling:**
    - [ ] Plugin handles missing fields gracefully (logs warning, continues processing)
    - [ ] Plugin handles wrong data types (int instead of str, null instead of dict)
    - [ ] Plugin handles null/None values without crashing
    - [ ] Plugin skips invalid data points (logs details, returns empty list for that document)
    - [ ] Plugin never crashes on malformed input (wrapped in try/except)
    - [ ] Error messages include enough context to debug (document keys, values, filters)
    
    **Type Safety:**
    - [ ] All `dict.get()` calls on nested objects check: `if isinstance(obj, dict)` first
    - [ ] All dimension values are validated as strings (or converted: `str(value)`)
    - [ ] All metric values validated with `is_valid_float()` to prevent inf/nan
    - [ ] Nested dictionary access checks each level:
        ```python
        config = json_body.get("config", {})
        if isinstance(config, dict):
            value = config.get("field")
            if isinstance(value, expected_type):
                # Use value safely
        ```
    - [ ] Type mismatches logged with details (expected vs actual type)
    
    **Logging:**
    - [ ] Plugin logs extraction start with context:
        ```python
        logger.info("plugin.extract.start", extra={
            "document_keys": list(json_body.keys())[:10],
            "filters": {...}
        })
        ```
    - [ ] Plugin logs extraction results:
        ```python
        logger.info("plugin.extract.complete", extra={
            "metrics_extracted": len(points),
            "metric_ids": [p.metric_name for p in points[:5]]
        })
        ```
    - [ ] Plugin logs skipped documents with reason:
        ```python
        logger.debug("plugin.extract.skipped", extra={
            "reason": "missing_timestamp",
            "document_id": refs.get("id")
        })
        ```
    - [ ] Plugin logs validation failures:
        ```python
        logger.warning("plugin.extract.validation_failed", extra={
            "field": "latency_ms",
            "value": raw_value,
            "expected_type": "float"
        })
        ```
    - [ ] All log messages use structured format with `extra={}` dict
    - [ ] No sensitive data in logs (redact PII, credentials, tokens)
    
    **Performance:**
    - [ ] Plugin doesn't create high-cardinality dimensions (verify each dimension has <500 unique values)
    - [ ] Plugin uses backend aggregations for large datasets if backend supports it
    - [ ] Plugin doesn't fetch unnecessary fields from source (only what's needed)
    - [ ] Plugin doesn't perform expensive operations in loops (move outside loop if possible)
    - [ ] Plugin returns early when filters don't match (don't process unnecessary data)
    
    **Testing:**
    - [ ] Test fixtures include edge cases:
        - [ ] Document with missing optional fields
        - [ ] Document with wrong data types (string instead of number, etc.)
        - [ ] Document with null/None values
        - [ ] Document with very large metric values (test overflow handling)
        - [ ] Document with very small/negative metric values
        - [ ] Document with unusual dimension values (empty strings, special characters)
        - [ ] Document with missing required fields
    - [ ] Plugin unit tests pass: `pytest tests/test_your_plugin.py -v`
    - [ ] Plugin handles multi-sample data correctly (if applicable)
    - [ ] All validation logic has test coverage
    
    **Code Quality:**
    - [ ] Plugin has clear docstring explaining what it extracts
    - [ ] Helper methods have docstrings
    - [ ] Complex logic has inline comments explaining "why"
    - [ ] No TODOs remaining in production code paths
    - [ ] Type hints on all method signatures
    - [ ] Plugin registered in `src/domain/plugins/__init__.py`
    
    **Configuration:**
    - [ ] Plugin `id` matches what's in `config.json` enabled_plugins
    - [ ] Plugin `kpis` list includes all primary metrics
    - [ ] Plugin `glossary` dict has entries for all extracted metrics (or references external JSON)
    - [ ] Filter parameters match what's passed from adapter
    
    **Quick Validation Commands:**
    
    ```bash
    # 1. Test plugin in isolation with edge case fixture
    python scripts/test_plugin.py --plugin your-plugin \
        --sample tests/fixtures/your-domain/edge_cases.json \
        --verbose
    
    # 2. Run plugin tests with debug logging
    LOG_LEVEL=DEBUG pytest tests/test_your_plugin.py -v -s
    
    # 3. Check for type safety issues
    # Review plugin code for dict.get() without isinstance() checks
    grep -n "\.get(" src/domain/plugins/your_plugin.py
    
    # 4. Verify logging is structured
    # Check that all logger calls use extra={} parameter
    grep -n "logger\." src/domain/plugins/your_plugin.py | grep -v "extra="
    
    # 5. Run full test suite
    pytest tests/test_your_plugin.py -v --tb=short
    ```
    
    **Common Issues to Check:**
    
    | Issue | Symptom | Fix |
    |-------|---------|-----|
    | Missing type checks | `TypeError: 'NoneType' object is not subscriptable` | Add `if isinstance(obj, dict)` before `obj.get()` |
    | Invalid floats | Metrics show "inf" or "nan" | Wrap with `if is_valid_float(value)` |
    | High cardinality | Slow queries, high memory | Reduce dimension unique values to <500 |
    | Missing logging | Can't debug prod issues | Add structured logging at start/end/errors |
    | No error handling | Plugin crashes on bad data | Wrap in try/except, log and continue |
    | Wrong types | Filter comparison fails silently | Ensure dimensions are strings, not ints |
    
    **Checkpoint:** If any checklist item fails, fix before Phase 5. 
    
    Production issues are 10x harder to debug than test failures. Take the time now to build robust code.
    
    **Gate:** All required checklist items must pass before proceeding to Phase 5 query validation.

---

## Phase 5: Fine-Tuning & Query Validation

**Goal:** Validate the Domain MCP works with real-world queries and meets user expectations.

### 5.1. Collect Real-World Queries

- [ ] **5.1.1. List Your Actual Use Cases**
    *   Write down 10-15 natural language queries you'll actually ask:
        - ✅ Include typical daily queries ("Show me API latency today")
        - ✅ Include complex queries ("Compare p95 latency between regions for the last week")
        - ✅ Include edge cases ("What's the error rate when there are no errors?")
        - ✅ Include queries with multiple filters ("Show checkout time in APAC for mobile users")
    *   Save these in a file: `docs/example_queries.md`

- [ ] **5.1.2. Categorize Queries by Complexity**
    *   **Simple:** Single KPI, no filters, short time range
        - Example: "Show me page load time today"
    *   **Medium:** Multiple filters or aggregations
        - Example: "What's the p95 API latency in us-west?"
    *   **Complex:** Multiple KPIs, dimensions, comparisons
        - Example: "Compare error rate between production and staging for the last 7 days"

### 5.2. End-to-End Query Testing

**Prerequisites:** 
- Your Domain MCP server is running
- Claude Desktop (or other MCP client) is configured to connect to your server
- **See:** `docs/testing-with-claude-desktop.md` for detailed setup instructions

- [ ] **5.2.1. Test Each Query (User + AI Assistant)**
    *   For each query in your list:
        1.  **User:** Ask the AI client (Claude, Cursor, etc.) the query
        2.  **Observe:** Watch what `get_key_metrics` call is generated
        3.  **Verify:** Check if results match your expectations
        4.  **Document:** Record which queries work and which don't

- [ ] **5.2.2. Validation Checklist for Each Query**
    *   For successful queries, verify:
        - [ ] Correct KPI extracted (metric_name matches intent)
        - [ ] Correct time range applied (start_time, end_time)
        - [ ] Filters applied correctly (dimensions match)
        - [ ] Results make sense (values are reasonable)
        - [ ] Units displayed correctly
    *   For failed/incorrect queries, document:
        - What query was asked?
        - What did you expect?
        - What actually happened?
        - Why did it fail? (missing KPI, wrong dimension, misunderstood query, etc.)

### 5.3. Identify and Fix Gaps

- [ ] **5.3.1. Common Failure Patterns**
    *   **LLM doesn't understand domain term:**
        - Fix: Add to glossary with more examples
        - Example: LLM doesn't know "TTFB" → Add to `glossary/kpis.json` with clear definition
    *   **Missing KPI:**
        - Fix: Add to plugin extraction logic
        - Update glossary
    *   **Missing dimension/filter:**
        - Fix: Add dimension to plugin
        - Follow Filter Alignment Checklist (4 locations)
        - Update glossary dimensions
    *   **Wrong aggregation applied:**
        - Fix: Update glossary to specify correct aggregations
        - Example: "error_rate" should use "sum" not "mean"
    *   **Time range misunderstood:**
        - Fix: Add examples to glossary showing time range queries
        - Example: "last week", "yesterday", "past 7 days"

- [ ] **5.3.2. Iterate on Implementation**
    *   For each identified gap:
        1.  Update glossary JSON files with clarifications
        2.  Add missing KPIs to plugin if needed
        3.  Add missing dimensions if needed (check cardinality!)
        4.  Re-run query to verify fix works
        5.  Update `docs/example_queries.md` with status: ✅ Works / ⚠️ Partial / ❌ Failed

- [ ] **5.3.3. Query Debugging Decision Tree**

    When a query doesn't work as expected, use this systematic diagnosis process:

    **Step 1: Was `get_key_metrics` called?**

    **Check:** Look at server logs for `get_key_metrics` invocation

    **If NO - LLM didn't invoke the tool:**
    - **Problem:** LLM didn't understand this is a metrics query
    - **Fix:** Enhance glossary with more query examples
    - **Action:** Add phrases similar to this query to `example_queries` in glossary
    - **Example:** User asked "How's performance?" - too vague
      - Add to glossary: "Show me [metric_name]", "What's the [metric_name]?"
    - **Retest:** Ask query again with more specific phrasing

    **If YES:** → Go to Step 2

    ---

    **Step 2: What parameters were passed to get_key_metrics?**

    **Check:** Log output shows parameters like:
    ```json
    {
      "metric_name": "page_load_time",
      "start_time": "2024-12-01T00:00:00Z",
      "end_time": "2024-12-08T23:59:59Z",
      "filters": {"region": "apac"}
    }
    ```

    **Diagnose each parameter:**

    **2a. Wrong metric_name?**
    - **Symptom:** Expected "ttfb", got "time_to_first_byte" or null
    - **Cause:** LLM doesn't know the canonical term
    - **Fix:** Update glossary
      - Make "ttfb" the primary `term` field
      - Add "time_to_first_byte" to `synonyms`
      - Add more `example_queries` using both terms
    - **Location:** `src/resources/glossary/*_kpis.json`

    **2b. Wrong or missing time range?**
    - **Symptom:** Expected "last 7 days", got "today only" or null
    - **Cause:** LLM misinterpreted time phrase
    - **Fix:** Add time range examples to glossary
    - **Examples to add:**
      - "last week" = 7 days ago to now
      - "this month" = beginning of month to now
      - "past 30 days" = 30 days ago to now
      - "yesterday" = previous day
    - **Add to multiple KPIs:** Helps LLM learn the pattern

    **2c. Missing or wrong filter?**
    - **Symptom:** Query said "in APAC" but no region filter passed
    - **Cause:** LLM doesn't know this phrase maps to a dimension
    - **Fix:** Update dimension glossary
      - Add to `example_usage`: "in APAC", "for APAC region", "APAC performance"
      - Add to synonyms: "APAC" = "apac", "Asia Pacific" = "apac"
    - **Location:** `src/resources/glossary/*_dimensions.json`
    - **Alternative:** Update `normalize.py` to parse this specific phrase

    **2d. Wrong aggregation?**
    - **Symptom:** Got mean, expected p95
    - **Cause:** Glossary doesn't specify preference or LLM chose default
    - **Fix:** Update KPI glossary
      - Reorder `aggregations` list - put preferred first: `["p95", "p99", "mean"]`
      - Add note: `"preferred_aggregation": "p95"`
      - Add to example queries: "What's the p95 [metric]?"
    - **Location:** `src/resources/glossary/*_kpis.json`

    **If all parameters look correct:** → Go to Step 3

    ---

    **Step 3: Did the adapter fetch data from source?**

    **Check:** Log shows "datasets_search returned X documents"

    **If 0 documents returned:**
    - **Problem:** Source has no data matching these parameters
    - **Debug steps:**
      1. Test source directly (bypass Domain MCP):
         ```bash
         # For Elasticsearch:
         curl -X GET "http://localhost:9200/my-index/_search" \
           -H "Content-Type: application/json" \
           -d '{"query": {"match_all": {}}}'
         
         # Check if ANY documents exist in your index
         ```
      2. Check if filters are too restrictive:
         - Try query without filters
         - Try with broader time range
      3. Check if time range is outside available data:
         - Verify you have data in the requested time range
         - Check timestamp field format matches what parser expects
      4. Check adapter query syntax:
         - Enable DEBUG logging: `export LOG_LEVEL=DEBUG`
         - Look for "ES Query DSL: {...}" in logs
         - Verify query syntax is valid for your source

    **If documents were returned:** → Go to Step 4

    ---

    **Step 4: Did the plugin extract metrics from the documents?**

    **Check:** Log shows "Extracted Y metrics from X documents"

    **If 0 metrics extracted (but documents were fetched):**
    - **Problem:** Plugin didn't recognize document structure or filtered them all out
    - **Debug steps:**
      1. **Check event type filtering:**
         ```python
         # In your plugin's extract() method, check:
         if json_body.get("event_type") != "page_load":
             return []  # ← Is this too restrictive?
         ```
         - Print the actual event_type from documents
         - Verify it matches your plugin's expected value
      
      2. **Check required fields:**
         ```python
         # Is your plugin rejecting documents with missing fields?
         if not json_body.get("metrics", {}).get("ttfb_ms"):
             return []  # ← Too strict?
         ```
         - Print the full json_body structure
         - Verify expected fields exist
      
      3. **Check filter logic:**
         ```python
         # Are your filter checks too strict?
         if region_filter and region != region_filter:
             return []  # ← Is 'region' getting extracted correctly?
         ```
         - Print dimension values before filtering
         - Verify filter comparisons are working

    **Quick test with isolated plugin:**
    ```bash
    python scripts/test_plugin.py \
      --plugin your-plugin \
      --sample tests/fixtures/your-domain/source_sample.json \
      --verbose
    
    # This runs your plugin on test data without full server
    # Check if it extracts metrics from your test fixtures
    ```

    **If metrics were extracted:** → Go to Step 5

    ---

    **Step 5: Are the extracted metrics correct?**

    **Check:** Compare extracted values with expected values

    **Common Issues:**

    **5a. Wrong unit?**
    - **Symptom:** Expected milliseconds, got seconds (off by 1000x)
    - **Cause:** Source data unit doesn't match glossary unit
    - **Fix:** Add unit conversion in plugin
    - **Example:**
      ```python
      # Source has seconds, glossary expects ms
      value_ms = json_body.get("duration_seconds") * 1000
      
      # Source has ms, glossary expects s
      value_s = json_body.get("duration_ms") / 1000
      ```
    - **Verify:** Check that `unit` field in MetricPoint matches glossary

    **5b. Wrong dimension values?**
    - **Symptom:** Expected region="apac", got region="asia-pacific"
    - **Cause:** Source uses different naming than glossary
    - **Fix:** Add dimension value transformation in plugin
    - **Example:**
      ```python
      # Normalize region values
      region_map = {
          "asia-pacific": "apac",
          "us-east-1": "us-east",
          "eu-west-1": "eu-west"
      }
      region = region_map.get(raw_region, raw_region)
      ```

    **5c. Values seem wrong (too high/low)?**
    - **Symptom:** p95 shows 50,000ms (50 seconds) - seems too high
    - **Cause:** Could be real, or unit issue, or data quality problem
    - **Debug:**
      1. Check a few raw documents - are the source values really this high?
      2. Verify unit conversion (did you multiply instead of divide?)
      3. Check for outliers - maybe a few bad data points skew aggregation
      4. Compare with expected range in glossary
    - **Fix:** 
      - If data is correct, update glossary typical range
      - If unit issue, fix conversion
      - If outliers, consider adding filtering for invalid values

    **If everything looks correct but results still unexpected:** → Go to Step 6

    ---

    **Step 6: Aggregation or statistics issue?**

    **Check:** How are metrics being aggregated?

    **Common Issues:**

    - **Wrong aggregation function applied:**
      - Check: `src/domain/utils/statistics.py` 
      - Verify percentile calculations are correct
      - Verify mean/sum/count logic
    
    - **Source-side vs domain-side aggregation conflict:**
      - If using source-side aggregation (ES aggregations, SQL GROUP BY)
      - And also doing domain-side aggregation
      - Results may be "aggregation of aggregations" (wrong!)
      - **Fix:** Choose one approach - source-side OR domain-side, not both

    - **Insufficient data points:**
      - P95 of 10 values is not statistically meaningful
      - Check how many data points were aggregated
      - May need larger time range or fewer filters

    ---

    **Step 7: Still not working?**

    **Enable verbose debug logging:**
    ```bash
    export LOG_LEVEL=DEBUG
    python -m src.server.cli run --host 0.0.0.0 --port 8000
    ```

    **Check these specific log points:**
    1. **normalize_request:** What was parsed from the query?
    2. **datasets_search:** What query was sent to source? How many documents returned?
    3. **plugin.extract:** How many documents processed? How many metrics extracted?
    4. **aggregate_metrics:** What values were aggregated? What was the result?

    **Collect this information to share:**
    - **Full query text:** Exact natural language query you asked
    - **Expected result:** What you thought would happen
    - **Actual result:** What actually happened (or error message)
    - **Relevant log excerpts:** From the 4 checkpoints above
    - **Sample document:** One example document from your source (redact sensitive data)

    **Common "gotcha" checklist:**
    - [ ] Timestamp field name matches what plugin expects?
    - [ ] Timestamp format parseable by `parse_timestamp()`?
    - [ ] Filter field names match source schema exactly (case-sensitive)?
    - [ ] Dimension values are strings, not integers or other types?
    - [ ] Plugin is registered in `src/domain/plugins/__init__.py`?
    - [ ] Config.json has correct Source MCP connection?
    - [ ] Source MCP is actually running and reachable?

### 5.4. Optimize Query Understanding

- [ ] **5.4.1. Enhance Glossary with Query Examples**
    *   For KPIs that work well, add more natural language examples:
    ```json
    {
      "term": "page_load_time",
      "example_queries": [
        "Show me page load time for the homepage",
        "What's the average page load time in APAC?",
        "Compare page load time to last week",
        "Page load performance in production"
      ]
    }
    ```
    *   For dimensions, add usage examples:
    ```json
    {
      "term": "region",
      "example_usage": [
        "in us-west",
        "for APAC",
        "across all regions",
        "by region"
      ]
    }
    ```

- [ ] **5.4.2. Document Synonyms and Abbreviations**
    *   If your domain uses multiple terms for the same thing:
    ```json
    {
      "term": "ttfb",
      "synonyms": ["time to first byte", "TTFB", "first byte time"],
      "definition": "Time from request start to first byte received"
    }
    ```

- [ ] **5.4.3. Add Domain-Specific Context**
    *   Update glossary with domain context that helps LLM understand:
        - Normal value ranges: "Typical page load time: 100-500ms"
        - When to use which KPI: "Use `page_load_time` for full page, `ttfb` for server response"
        - Common comparisons: "Usually compared by region and device type"

### 5.5. Create Query Test Suite

- [ ] **5.5.1. Document Working Queries**
    *   Create `docs/example_queries.md` with:
        - ✅ Queries that work perfectly
        - Query → Expected result
        - Any tips for phrasing
    *   This becomes your onboarding doc for new team members

- [ ] **5.5.2. Automated Query Testing (Optional)**
    *   If needed, create tests that simulate natural language queries:
    ```python
    # tests/test_query_validation.py
    def test_common_queries():
        # Query: "Show me API latency today"
        result = ask_llm("Show me API latency today")
        assert result.metric_name == "api_latency"
        assert result.time_range == "today"
    ```

### 5.6. Performance & Usability Check

- [ ] **5.6.1. Query Response Time**
    *   Test each query type and measure response time:
        - Simple queries: Should complete in < 5 seconds
        - Medium queries: Should complete in < 15 seconds
        - Complex queries: Should complete in < 30 seconds
    *   If too slow, optimize:
        - Use source-side aggregations (ES aggregations, SQL GROUP BY)
        - Reduce default time ranges
        - Add pagination
        - Add query result limits

- [ ] **5.6.2. User Satisfaction Check**
    *   Ask yourself (or team members):
        - [ ] Do results answer the question I asked?
        - [ ] Are results formatted clearly?
        - [ ] Do I trust the data?
        - [ ] Would I use this daily?
        - [ ] Are error messages helpful when queries fail?

**Checkpoint:** If 80%+ of your real-world queries work correctly, proceed to Phase 6.

---

## Phase 6: Delivery & Documentation

**Goal:** Finalize and deploy the Domain MCP.

- [ ] **6.1. Final Review**
    *   Check `AGENTS.md` for any remaining "Template" references.
    *   Verify `README.md` instructions are accurate for the *new* project.
    *   Ensure `docs/example_queries.md` is complete with working examples.

- [ ] **6.2. Deployment Preparation**
    *   Document deployment steps for your environment
    *   Update configuration for production (URLs, credentials, limits)
    *   Set up monitoring and logging

- [ ] **6.3. Team Onboarding**
    *   Share `docs/example_queries.md` with team
    *   Demonstrate 5-10 common queries
    *   Collect feedback and iterate if needed

- [ ] **6.4. Completion**
    *   Archive this `IMPLEMENTATION_PLAN.md` (or delete it)
    *   Celebrate! 🎉 You've built a working Domain MCP

---

## Developer Notes

### ⚠️ Filter Alignment Checklist (CRITICAL!)

When adding a **new filter** (e.g., `region`, `endpoint_category`, `user_tier`), you MUST update these 4 locations:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. src/server/normalize.py                                      │
│    └─ Parse filter from natural language query                  │
│       Example: "in us-west" → {"region": "us-west"}             │
├─────────────────────────────────────────────────────────────────┤
│ 2. src/server/app.py (or http.py)                               │
│    └─ Pass filter parameter to adapter call                     │
│       Example: datasets_search(..., region=region_filter)       │
├─────────────────────────────────────────────────────────────────┤
│ 3. src/adapters/your_adapter.py                                 │
│    └─ Translate filter to source query language                 │
│       ES: Add to Query DSL {"term": {"region": "us-west"}}      │
│       SQL: Add to WHERE clause                                   │
├─────────────────────────────────────────────────────────────────┤
│ 4. src/domain/plugins/your_plugin.py (optional)                 │
│    └─ Post-filter if source filtering incomplete                │
│       Example: if region_filter and dims["region"] != ...       │
└─────────────────────────────────────────────────────────────────┘
```

**Testing your filter:**
- [ ] Query with filter returns filtered results
- [ ] Query without filter returns all results
- [ ] Invalid filter value returns empty results (not error)
- [ ] Check adapter's source query (ES Query DSL, SQL, etc.) includes filter

---

### 🚨 High-Cardinality Dimension Warning

**Before** adding a dimension, check how many unique values it has:

| Cardinality | Example | Impact | Recommendation |
|-------------|---------|--------|----------------|
| Low (< 50) | `region`, `device_type` | ✅ Safe | Use as-is |
| Medium (50-500) | `page_type`, `api_endpoint_category` | ⚠️ Monitor | Acceptable, watch query performance |
| High (500+) | `user_id`, `session_id`, `url` | ❌ Danger | **Don't use as dimension!** |
| Very High (10k+) | `transaction_id`, `/product/12345` | 🔥 Critical | Store separately, not as dimension |

**Solutions for high-cardinality fields:**
- **Group them:** `/api/product/123` → `api_product` (category)
- **Parameterize:** `/api/product/:id` instead of raw URL with ID
- **Store as metadata:** Keep in raw data, don't expose as filterable dimension
- **Use separate field:** Create `endpoint_category` field in addition to raw `endpoint`

**Why this matters:**
- High cardinality causes slow queries and excessive memory usage
- Metrics storage systems struggle with millions of unique dimension combinations
- Query performance degrades exponentially with cardinality
