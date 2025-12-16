# Example Queries for [Your Domain Name]

> **Instructions:** Copy this file to `example_queries.md` and fill in with your actual queries during Phase 5 of implementation.

**Last Updated:** [Date]  
**Domain:** [Your Domain - e.g., Web Performance Testing, Payment Analytics, etc.]  
**Status:** 🟢 Ready for Use / 🟡 In Progress / 🔴 Issues Found

---

## 🎯 Quick Start - Most Common Queries

These are the queries our team uses daily:

### 1. [Query Name/Purpose]
**Query:** "Show me [metric] for [time range]"

**Expected Result:**
- Metric: [metric_name]
- Time range: [actual range]
- Typical values: [range, e.g., 100-500ms]

**Status:** ✅ Works perfectly / ⚠️ Partial / ❌ Needs fixing

**Notes:** [Any tips for phrasing this query]

---

### 2. [Another Common Query]
**Query:** "[natural language query]"

**Expected Result:**
- [details]

**Status:** [✅/⚠️/❌]

---

## 📊 Queries by Category

### Simple Queries (Single KPI, No Filters)

#### ✅ Current Performance
```
Query: "Show me page load time today"
Result: page_load_time metric for today
Notes: Works with "today", "yesterday", "this week"
```

#### ✅ [Add More Simple Queries]
```
Query: 
Result:
Notes:
```

---

### Medium Complexity (Filters or Aggregations)

#### ✅ Regional Performance
```
Query: "What's the p95 API latency in us-west?"
Result: api_latency metric, p95 aggregation, filtered to region=us-west
Filters Applied: region
Aggregation: p95
Notes: Can substitute any region: us-east, eu-central, apac
```

#### ⚠️ [Partially Working Query]
```
Query: "Show error rate by device type"
Result: Works but doesn't group properly
Issue: Need to add group-by support
TODO: Update aggregation logic in plugin
```

---

### Complex Queries (Multiple Dimensions, Comparisons)

#### ✅ Performance Comparison
```
Query: "Compare page load time between Chrome and Firefox for the last week"
Result: page_load_time metric, filtered by browser, last 7 days
Dimensions: browser=chrome vs browser=firefox
Notes: LLM may generate two separate queries and compare
```

#### ❌ [Not Working Yet]
```
Query: "Show me checkout time trends for mobile users in APAC compared to last month"
Expected: checkout_duration metric, device_type=mobile, region=apac, time comparison
Actual: Fails - doesn't understand "compared to last month"
TODO: Add time comparison examples to glossary
```

---

## 🔤 Domain Terminology Guide

**Terms the LLM understands well:**
- "page load time" ✅ → page_load_time metric
- "API latency" ✅ → api_latency metric
- "TTFB" ✅ → ttfb metric (thanks to glossary)
- "in APAC" ✅ → region=apac filter
- "for mobile" ✅ → device_type=mobile filter

**Terms that need clarification:**
- "response time" → Could mean API latency or page load time (ambiguous)
  - Fix: Be specific: "API response time" or "page response time"
- "errors" → Could mean error_rate or error_count
  - Fix: Specify: "error rate percentage" or "number of errors"

**Synonyms that work:**
- "last week" = "past 7 days" = "previous week" ✅
- "p95" = "95th percentile" = "95 percentile" ✅

---

## 📝 Query Templates

Use these templates for consistent results:

### For a Single Metric
```
"Show me [metric_name] [time_range]"
"What's the [metric_name] [time_range]?"
"Display [metric_name] for [time_range]"

Examples:
- "Show me page load time today"
- "What's the API latency for the last 7 days?"
```

### With Regional Filter
```
"Show me [metric_name] in [region] [time_range]"
"What's the [metric_name] for [region]?"

Examples:
- "Show me page load time in us-west today"
- "What's the error rate for APAC this week?"
```

### With Multiple Filters
```
"Show me [metric_name] for [device_type] users in [region] [time_range]"

Examples:
- "Show me checkout time for mobile users in APAC this week"
- "What's the API latency for desktop in eu-central?"
```

### With Aggregations
```
"What's the [aggregation] [metric_name] [filters] [time_range]?"

Examples:
- "What's the p95 page load time in us-west today?"
- "Show me the average API latency for mobile users"
```

### Comparisons
```
"Compare [metric_name] between [dimension_value_1] and [dimension_value_2]"

Examples:
- "Compare page load time between Chrome and Firefox"
- "Compare error rate across all regions"
```

---

## 🚨 Known Limitations

### What Works Well ✅
- Single metric queries
- Time range filtering (today, yesterday, last week, specific dates)
- Regional filtering
- Device type filtering
- Percentile aggregations (p50, p95, p99)
- Simple comparisons

### What Needs Improvement ⚠️
- [ ] Time-based comparisons ("compared to last week")
- [ ] Multi-metric queries in single request
- [ ] Complex boolean filters ("mobile OR tablet")
- [ ] Queries involving calculations ("what's the difference between...")

### What Doesn't Work Yet ❌
- [ ] Natural language aggregations ("group by region and device")
- [ ] Anomaly detection ("show me unusual spikes")
- [ ] Forecasting ("predict next week's performance")

---

## 💡 Tips for Best Results

### Be Specific
❌ "Show me performance"  
✅ "Show me page load time for the last 7 days"

### Use Glossary Terms
❌ "How fast is the site?"  
✅ "What's the page load time?"

### Specify Time Ranges
❌ "Show me API latency"  
✅ "Show me API latency today"

### One Question at a Time
❌ "Show me page load time and error rate in all regions"  
✅ "Show me page load time in all regions" (then ask about error rate separately)

---

## 📈 Success Metrics

**Query Success Rate:** [XX]% of queries return expected results

**Most Used Queries:**
1. [Query 1] - used [X] times/day
2. [Query 2] - used [X] times/day
3. [Query 3] - used [X] times/day

**Response Times:**
- Simple queries: avg [X] seconds
- Complex queries: avg [X] seconds

---

## 🔄 Iteration Log

### [Date] - Initial Query Set
- Added 15 common queries
- 12/15 working (80% success rate)
- Need to add time comparison support

### [Date] - Added Regional Queries
- Added 5 region-specific queries
- All working after updating glossary with region examples

### [Date] - Fixed Device Type Filtering
- Issue: LLM didn't understand "mobile users"
- Fix: Added "mobile", "desktop", "tablet" examples to glossary
- Result: Now works consistently

---

## 📚 Related Documentation

- **Glossary:** `src/resources/glossary/[domain]_kpis.json`
- **Plugin:** `src/domain/plugins/[domain]_plugin.py`
- **Tests:** `tests/test_[domain]_plugin.py`

---

## 🤝 Contributing

When you discover a new useful query:
1. Test it multiple times to ensure consistency
2. Add it to this document under appropriate category
3. Note any caveats or tips for phrasing
4. Update glossary if needed to improve LLM understanding

