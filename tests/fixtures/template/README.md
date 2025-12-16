# Template Test Fixtures

This directory contains **template files** to help you create test fixtures for your domain plugin.

## What Are Fixtures?

Fixtures are sample data files used for testing. They contain:
1. **Sample input:** Raw data from your Source MCP (what your plugin receives)
2. **Expected output:** The `MetricPoint` objects your plugin should produce

## How to Use These Templates

### Step 1: Create Your Domain Fixture Directory

```bash
# Copy this template directory
cp -r tests/fixtures/template tests/fixtures/my_domain

# Replace "my_domain" with your actual domain name, e.g.:
# - webperf
# - payment_logs
# - api_metrics
```

### Step 2: Get Real Sample Data

Fetch actual data from your Source MCP to use as test input:

**For Elasticsearch:**
```bash
# Use ES search API to get sample documents
curl -X GET "http://localhost:9200/my-index/_search?size=3" \
  -H "Content-Type: application/json" \
  -d '{"query": {"match_all": {}}}' > tests/fixtures/my_domain/source_response_sample.json
```

**For Horreum:**
```python
# Use adapter to fetch sample
from src.adapters.horreum import HorreumAdapter
adapter = HorreumAdapter(config)
result = await adapter.datasets_search(test_id="123", limit=3)
# Save result to tests/fixtures/my_domain/source_response_sample.json
```

**Manual approach:**
- Copy example responses from your Source MCP documentation
- Use `scripts/verify_connection.py` output as reference
- Check existing fixtures in `tests/fixtures/elasticsearch-logs/` or `tests/fixtures/boot-time/`

### Step 3: Define Expected Output

Based on your sample input, manually write what your plugin **should** extract:

1. Open `tests/fixtures/my_domain/expected_metrics.json`
2. For each document in your sample input:
   - What timestamp should be extracted?
   - What metric value(s)?
   - What dimensions?
   - What unit?
3. Write these as `MetricPoint` JSON objects

### Step 4: Create Plugin Test

```bash
# Copy the template test
cp tests/test_template_plugin.py tests/test_my_domain_plugin.py

# Update the test to:
# - Import your plugin class
# - Load your fixtures (source_response_sample.json, expected_metrics.json)
# - Assert extracted metrics match expected
```

### Step 5: Run Your Test

```bash
pytest tests/test_my_domain_plugin.py -v
```

If it passes, your plugin extraction logic is correct! 🎉

## File Descriptions

| File | Purpose | Who Creates It |
|------|---------|----------------|
| `source_response_sample.json` | Raw data from Source MCP | You (fetch from actual source) |
| `expected_metrics.json` | What plugin should extract | You (write manually) |
| `README.md` | This guide | Template (delete after reading) |

## Required Test Scenarios

Your fixtures should cover these specific scenarios (minimum):

### Scenario 1: Happy Path ✅ REQUIRED
**Purpose:** Verify plugin works with perfect data

**Sample document characteristics:**
- All required fields present and valid
- All optional fields present
- Standard data types (no edge cases)
- Timestamp in expected format
- Metric values in normal range

**Expected result:** All metrics extracted correctly

**Example document:**
```json
{
  "@timestamp": "2024-12-15T10:30:45Z",
  "event_type": "page_load",
  "metrics": {
    "page_load_ms": 1250,
    "ttfb_ms": 145
  },
  "user": {
    "region": "us-west",
    "device": "desktop"
  }
}
```

---

### Scenario 2: Missing Optional Fields ✅ REQUIRED
**Purpose:** Verify plugin handles incomplete data gracefully

**Sample document characteristics:**
- Required fields present (timestamp, event_type)
- Some optional metrics missing
- Some dimensions missing or null

**Expected result:** 
- Extracts available metrics
- Skips missing metrics (doesn't crash)
- Dimensions with null values show as "unknown" or are omitted

**Example document:**
```json
{
  "@timestamp": "2024-12-15T11:00:00Z",
  "event_type": "page_load",
  "metrics": {
    "page_load_ms": 980
    // ttfb_ms is missing - should be handled gracefully
  },
  "user": {
    "region": "apac"
    // device is missing - should be handled gracefully
  }
}
```

---

### Scenario 3: Invalid/Edge Case Values ✅ REQUIRED
**Purpose:** Verify plugin validates and sanitizes data

**Sample document characteristics:**
- Timestamp: Different format than usual (test timestamp parser flexibility)
- Metric value: Negative number, zero, or very large number
- String field: Empty string, "null", "N/A"
- Dimension: Unexpected value (not in glossary's valid values list)

**Expected result:**
- Invalid values logged as warnings
- Documents with invalid critical data skipped (or sanitized)
- No crashes or exceptions
- Plugin continues processing other valid documents

**Example document:**
```json
{
  "@timestamp": "2024-12-15T12:00:00.123456Z",  // More precision than usual
  "event_type": "page_load",
  "metrics": {
    "page_load_ms": -50,  // Negative - invalid!
    "ttfb_ms": 999999     // Suspiciously high
  },
  "user": {
    "region": "unknown-region",  // Not in valid values list
    "device": ""  // Empty string
  }
}
```

---

### Scenario 4: Multiple Event Types ⚠️ CONDITIONAL
**Purpose:** Verify plugin correctly filters by event type

**When needed:** If your data source has multiple event types (page_load, api_call, error, etc.)

**Sample document characteristics:**
- Mix of relevant and irrelevant event types
- Example: 2 page_load events, 1 api_call event, 1 error event

**Expected result:**
- Only relevant event types processed
- Irrelevant events skipped (return empty list)
- No errors when encountering unexpected event types

**Example documents:**
```json
[
  {
    "@timestamp": "2024-12-15T13:00:00Z",
    "event_type": "page_load",  // ✅ Process this
    "metrics": {"page_load_ms": 1100}
  },
  {
    "@timestamp": "2024-12-15T13:01:00Z",
    "event_type": "api_call",  // ❌ Skip this (different plugin)
    "metrics": {"api_duration_ms": 45}
  },
  {
    "@timestamp": "2024-12-15T13:02:00Z",
    "event_type": "page_load",  // ✅ Process this
    "metrics": {"page_load_ms": 980}
  }
]
```

---

### Scenario 5: Unit Conversion ⚠️ CONDITIONAL
**Purpose:** Verify plugin correctly converts units

**When needed:** If source data uses different units than your KPIs

**Sample document characteristics:**
- Source has milliseconds, KPI expects seconds
- Source has bytes, KPI expects megabytes
- Source has percentages as decimals (0.95), KPI expects whole numbers (95)

**Expected result:**
- Values correctly converted
- Unit field matches glossary definition

**Example document:**
```json
{
  "@timestamp": "2024-12-15T14:00:00Z",
  "event_type": "page_load",
  "metrics": {
    "page_load_seconds": 1.25,  // Source has seconds
    "transfer_bytes": 524288     // Source has bytes
  }
}
```

**Expected output:**
```json
[
  {
    "metric_name": "page_load_time",
    "value": 1250,  // Converted to ms
    "unit": "ms",
    "timestamp": "2024-12-15T14:00:00Z"
  },
  {
    "metric_name": "transfer_size",
    "value": 0.5,  // Converted to MB
    "unit": "MB",
    "timestamp": "2024-12-15T14:00:00Z"
  }
]
```

---

### Scenario 6: High-Cardinality Dimension ⚠️ CONDITIONAL
**Purpose:** Verify plugin doesn't extract unbounded dimensions

**When needed:** If source has fields like user_id, session_id, full URL path

**Sample document characteristics:**
- Documents with high-cardinality fields present (user_id, session_id, etc.)
- These fields should NOT become dimensions

**Expected result:**
- High-cardinality fields NOT added to dimensions dict
- Or: High-cardinality fields transformed to low-cardinality categories
- Example: `/product/12345` → `"product_page"`, `/checkout/step-2` → `"checkout"`

**Example document:**
```json
{
  "@timestamp": "2024-12-15T15:00:00Z",
  "event_type": "page_load",
  "url": "/product/laptop-abc-12345",  // High cardinality - don't use as-is!
  "user_id": "user_987654",            // High cardinality - don't use!
  "session_id": "sess_abc123def456",   // High cardinality - don't use!
  "page_type": "product",              // Low cardinality - GOOD to use
  "metrics": {"page_load_ms": 1150}
}
```

**Expected output:**
```json
{
  "metric_name": "page_load_time",
  "value": 1150,
  "unit": "ms",
  "dimensions": {
    "page_type": "product"
    // Note: url, user_id, session_id are NOT in dimensions
  },
  "timestamp": "2024-12-15T15:00:00Z"
}
```

---

## Minimum Coverage Requirements

**For Phase 4 validation (Technical Validation):**
- ✅ Scenarios 1-3 MUST be covered (happy path, missing fields, invalid values)
- ✅ At least 3 sample documents total
- ✅ Expected metrics JSON matches actual plugin output exactly
- ✅ Unit test passes: `pytest tests/test_my_plugin.py -v`

**For Phase 5 readiness (Query Validation):**
- ✅ All required scenarios covered (1-3)
- ✅ Applicable conditional scenarios covered (4-6 if relevant to your domain)
- ✅ At least 5 sample documents covering different combinations

**For production deployment:**
- ✅ All applicable scenarios covered (including conditional ones)
- ✅ At least 5-10 sample documents representing real data diversity
- ✅ Integration test passes with real Source MCP data
- ✅ Edge cases from actual production data included

---

## AI Agent Checklist

When reviewing a user's fixtures, verify:

**Document Count:**
- [ ] At least 3 documents in `source_response_sample.json`?
- [ ] Documents represent different scenarios (not all identical)?

**Required Scenarios:**
- [ ] **Scenario 1 (Happy path):** At least 1 document with all fields present?
- [ ] **Scenario 2 (Missing data):** At least 1 document with some fields missing?
- [ ] **Scenario 3 (Edge cases):** At least 1 document with invalid/unusual values?

**Conditional Scenarios (check if applicable):**
- [ ] **Scenario 4:** If multiple event types exist, are they tested?
- [ ] **Scenario 5:** If unit conversion needed, is it tested?
- [ ] **Scenario 6:** If high-cardinality fields exist, are they excluded from dimensions?

**Expected Output:**
- [ ] `expected_metrics.json` has correct format (array of MetricPoint objects)?
- [ ] Number of MetricPoints makes sense for input documents?
- [ ] All required fields present: `metric_name`, `value`, `unit`, `timestamp`, `dimensions`?
- [ ] Units in expected output match glossary definitions exactly?

**Quality Checks:**
- [ ] Timestamps are valid ISO 8601 format?
- [ ] Metric values are reasonable (not obviously wrong)?
- [ ] Dimensions use snake_case keys matching glossary?
- [ ] No high-cardinality values in dimensions?

**If any checklist item is NO:** Guide user to add missing scenario or fix issue.

**Quick Validation:**
```bash
# Test the fixtures
python scripts/test_plugin.py \
  --plugin your-plugin \
  --sample tests/fixtures/your-domain/source_response_sample.json \
  --expected tests/fixtures/your-domain/expected_metrics.json

# Should output: "✅ All scenarios covered, extraction matches expected"
```

---

## Tips

### Keep Fixtures Realistic
- Use **real data** from your source (redact sensitive info)
- Include **edge cases**: missing fields, null values, different event types
- Add **multiple documents** (3-5 minimum) to test various scenarios
- Don't create "perfect" synthetic data - real data has quirks!

### Document Your Test Cases
Add comments to your fixture files explaining what each document tests:
```json
{
  "_comment": "Scenario 1: Happy path - all fields present",
  "@timestamp": "2024-12-15T10:00:00Z",
  ...
}
```

### Common Mistakes
❌ **Fixture doesn't match actual data structure**
  - Solution: Copy real response from your source, don't guess

❌ **Expected output has wrong field names**
  - Solution: Check `MetricPoint` model in `src/domain/models.py`

❌ **Units don't match between fixture and plugin**
  - Solution: Standardize on short units (`ms`, `s`, `bytes`)

## Examples

See working examples:
- **Elasticsearch:** `tests/fixtures/elasticsearch-logs/`
- **Horreum:** `tests/fixtures/boot-time/`

## Cleanup

Once you've created your domain fixtures and tests pass:
```bash
# Delete this template directory
rm -rf tests/fixtures/template
```
