# Glossary Organization Guide

This directory contains glossary files that help AI clients understand your domain terminology.

## 📋 What Are Glossaries?

Glossaries serve **two purposes**:

1. **Documentation** - Team reference for KPIs, dimensions, and terminology
2. **LLM Context** - Exposed as MCP Resources for AI clients to read and understand your domain

When a user asks Claude: *"What's the p95 TTFB in APAC?"*, Claude reads your glossaries to understand:
- TTFB = Time to First Byte (from KPI glossary)
- APAC = Asia Pacific region (from dimension glossary)
- p95 = 95th percentile (from aggregation preferences)

---

## 🏗️ Recommended Organization

### Modular by Concern (Recommended)

Organize glossaries by **logical grouping**, not by "KPIs vs dimensions":

```
glossary/
├── README.md (this file)
├── core_metrics.json          # Your primary KPIs
├── derived_metrics.json        # Computed/secondary metrics
├── geographic_regions.json     # Region taxonomy (reusable!)
├── device_types.json           # Device taxonomy (reusable!)
├── business_context.json       # Value ranges, thresholds, SLOs
└── synonyms_acronyms.json      # Common abbreviations
```

**Why modular?**
- ✅ **Reusability:** Multiple plugins can share `geographic_regions.json`
- ✅ **Maintainability:** Update region definitions in one place
- ✅ **Clarity:** Each file has single responsibility
- ✅ **Team collaboration:** Different teams can own different files
- ✅ **Versioning:** Easier to track changes to specific concepts

### Monolithic (Not Recommended)

```
glossary/
├── all_kpis.json      # 50+ metrics in one file - hard to maintain
└── all_dimensions.json # 30+ dimensions - becomes unwieldy
```

**Problems:**
- ❌ Hard to find specific entries
- ❌ Merge conflicts in large files
- ❌ Can't reuse subsets
- ❌ No clear ownership

---

## 📝 File Naming Convention

Use descriptive, specific names:

✅ **Good:**
- `webperf_core_vitals.json` - Clear, specific
- `payment_methods.json` - Reusable concept
- `aws_regions.json` - Standard taxonomy
- `slo_thresholds.json` - Business rules

❌ **Bad:**
- `kpis.json` - Too generic
- `stuff.json` - Meaningless
- `myfile.json` - Not descriptive
- `temp.json` - Suggests throwaway

**Pattern:** `{domain}_{concept}.json`
- Use lowercase with underscores
- Be specific: `payment_methods` not just `methods`
- Group related concepts: `webperf_*` files together

---

## 🗂️ Example Organization Patterns

### Pattern 1: Web Performance Domain

```
glossary/
├── webperf_core_vitals.json       # LCP, FID, CLS
├── webperf_custom_metrics.json    # Custom timing metrics
├── webperf_regions.json            # Geographic regions
├── webperf_devices.json            # Device types, browsers
├── webperf_pages.json              # Page type taxonomy
└── webperf_thresholds.json         # Performance budgets, SLOs
```

### Pattern 2: E-commerce Domain

```
glossary/
├── sales_revenue_metrics.json      # Revenue, conversion, AOV
├── sales_order_metrics.json        # Orders, items, returns
├── customer_segments.json          # User tiers, cohorts
├── product_categories.json         # Taxonomy of products
├── geographic_markets.json         # Regions, countries
└── business_goals.json             # Targets, benchmarks
```

### Pattern 3: Infrastructure Monitoring

```
glossary/
├── compute_metrics.json            # CPU, memory, disk
├── network_metrics.json            # Bandwidth, latency, packets
├── service_health.json             # Availability, errors
├── cloud_providers.json            # AWS, GCP, Azure taxonomies
├── environments.json               # prod, staging, dev
└── alert_thresholds.json           # Critical/warning levels
```

### Pattern 4: Shared Taxonomies (Reusable)

If multiple domains share concepts, extract to shared files:

```
glossary/
├── shared/
│   ├── iso_3166_countries.json     # Standard country codes
│   ├── iana_time_zones.json        # Standard time zones
│   ├── http_status_codes.json      # Standard HTTP codes
│   └── currency_codes.json          # ISO 4217 currency codes
├── webperf/
│   ├── metrics.json
│   └── devices.json
└── sales/
    ├── metrics.json
    └── products.json
```

---

## 📐 Glossary File Structure

### KPI/Metric Entry

```json
{
  "term": "page_load_time",
  "full_name": "Page Load Time",
  "definition": "Time from navigation start to page fully loaded",
  "unit": "ms",
  "aggregations": ["p50", "p75", "p95", "p99", "mean"],
  "preferred_aggregation": "p95",
  "typical_range": "1000-3000ms for good performance",
  "alert_threshold": {
    "warning": 3000,
    "critical": 5000
  },
  "example_queries": [
    "What's the page load time?",
    "Show me p95 page load time",
    "How's page performance today?",
    "Compare page load time to last week"
  ],
  "synonyms": [
    "load time",
    "page speed",
    "time to loaded"
  ],
  "related_metrics": ["ttfb", "fcp", "lcp"],
  "business_impact": "Critical for user experience and conversion",
  "documentation_url": "https://wiki.example.com/metrics/page-load-time"
}
```

### Dimension Entry

```json
{
  "term": "region",
  "full_name": "Geographic Region",
  "definition": "Geographic region where the measurement was taken",
  "type": "categorical",
  "values": [
    "us-east",
    "us-west",
    "eu-west",
    "eu-central",
    "apac",
    "latam"
  ],
  "cardinality": 6,
  "example_usage": [
    "in APAC",
    "for us-west region",
    "across all regions",
    "by region",
    "in the US"
  ],
  "synonyms": {
    "apac": ["Asia Pacific", "APAC", "asia", "asian region"],
    "us-east": ["US East", "us-east-1", "east coast", "eastern US"],
    "eu-west": ["EU West", "Western Europe", "eu-west-1"]
  },
  "mapping_rules": {
    "us-east-1": "us-east",
    "us-east-2": "us-east",
    "us-west-1": "us-west",
    "us-west-2": "us-west"
  },
  "default_value": "unknown",
  "documentation_url": "https://wiki.example.com/dimensions/region"
}
```

### Taxonomy Entry (Hierarchical)

```json
{
  "term": "device_type",
  "definition": "Category of device used for measurement",
  "hierarchy": {
    "mobile": {
      "children": ["smartphone", "tablet"],
      "description": "Mobile devices"
    },
    "desktop": {
      "children": ["windows", "mac", "linux"],
      "description": "Desktop computers"
    }
  },
  "example_queries": [
    "on mobile devices",
    "for desktop users",
    "smartphone vs tablet"
  ]
}
```

---

## ✨ Best Practices

### 1. Use Short, Consistent Units

✅ **Good:**
```json
{"unit": "ms"}
{"unit": "s"}
{"unit": "bytes"}
{"unit": "count"}
{"unit": "%"}
```

❌ **Bad:**
```json
{"unit": "milliseconds"}  // Too verbose
{"unit": "MB"}            // Ambiguous (megabits vs megabytes)
{"unit": "percentage"}    // Use "%"
```

### 2. Provide Multiple Example Queries

Each KPI should have **5-10 example queries** showing different phrasings:

```json
{
  "example_queries": [
    "What's the API latency?",              // Simple
    "Show me p95 API latency",              // With aggregation
    "API latency in us-west",               // With dimension
    "Compare API latency to last week",     // Time comparison
    "How's the backend response time?",     // Synonym usage
    "API performance today",                // Conversational
    "Latency for checkout endpoint",        // With filter
    "p99 API latency by region"             // Complex
  ]
}
```

### 3. Document Value Ranges

Help LLMs validate results by documenting typical ranges:

```json
{
  "term": "error_rate",
  "typical_range": "0.1-2% is normal, >5% indicates issues",
  "alert_threshold": {
    "warning": 3,
    "critical": 5
  }
}
```

### 4. Cross-Reference Related Concepts

```json
{
  "term": "lcp",
  "related_metrics": ["fcp", "ttfb", "fid", "cls"],
  "note": "One of Core Web Vitals. Often analyzed together with FID and CLS."
}
```

### 5. Use Standard Taxonomies When Possible

Instead of inventing your own, use standards:
- **Countries:** ISO 3166-1 alpha-2 codes (`US`, `GB`, `JP`)
- **Languages:** ISO 639-1 codes (`en`, `es`, `fr`)
- **Currencies:** ISO 4217 codes (`USD`, `EUR`, `GBP`)
- **Time Zones:** IANA Time Zone Database (`America/New_York`, `Europe/London`)

### 6. Version Your Glossaries

Add version field to track changes:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "version": "2.1.0",
  "last_updated": "2025-12-16",
  "changelog": "Added new regions: latam, africa",
  ...
}
```

### 7. Keep Cardinality Low

Dimensions with >500 unique values cause performance issues:

✅ **Good (low cardinality):**
- `region`: 5-10 regions
- `device_type`: 3-5 categories
- `environment`: 3-4 environments (dev, staging, prod)

❌ **Bad (high cardinality):**
- `user_id`: millions of users
- `url`: thousands of unique URLs
- `session_id`: unique per session

**Solution:** Group high-cardinality fields into categories:
- `/api/product/123` → `api_product` (endpoint category)
- User ID → `user_tier` (free, pro, enterprise)

---

## 🔄 Updating Glossaries

### When to Update

Update glossaries when:
- ✅ Adding new metrics or dimensions
- ✅ Discovering new synonyms users are using
- ✅ Adjusting value ranges based on real data
- ✅ Adding more example queries
- ✅ Fixing misunderstandings (wrong definitions)

### How to Update

1. **Make changes** in appropriate glossary file
2. **Restart server** to load new glossary (or hot-reload if supported)
3. **Test queries** that use changed terms
4. **Document change** in version/changelog
5. **Notify team** of terminology updates

### Testing Glossary Changes

```bash
# 1. Validate JSON syntax
python -m json.tool src/resources/glossary/my_glossary.json

# 2. Restart server with new glossary
python -m src.server.cli run

# 3. Test affected queries in Claude Desktop
# Ask: "What's the <metric>?"
# Verify Claude understands the term

# 4. Check server logs for glossary load
# Look for: "Loaded glossary: my_glossary.json"
```

---

## 🎯 Migration from Templates

If you started with template files:

```bash
# 1. Copy templates to your domain files
cp template_kpis.json webperf_metrics.json
cp template_dimensions.json webperf_dimensions.json

# 2. Fill in your domain-specific content
# Replace all TODO markers with actual data

# 3. Split into modular files (optional but recommended)
# Extract regions → webperf_regions.json
# Extract devices → webperf_devices.json

# 4. Delete template files when done
rm template_*.json

# 5. Update plugin to reference new glossary files
# In your plugin, update glossary loading logic
```

---

## 📚 Examples

See these for inspiration:
- `boot_time_kpis.json` - Production example from PerfScale domain
- `os_identifiers.json` - Standard taxonomy example
- `platform_identifiers.json` - Hardware platform taxonomy

---

## ❓ FAQ

**Q: Should glossaries be in the repo or loaded externally?**
A: Start with repo (easier). Move to external CMS/API when they become large or need frequent updates by non-developers.

**Q: How many glossary files should I have?**
A: Start with 2-3 (metrics, dimensions, business context). Split further if files exceed 200 lines or team requests it.

**Q: Can I use YAML instead of JSON?**
A: Yes, but JSON is preferred for MCP Resource compatibility. Add YAML support in plugin if needed.

**Q: How do I handle sensitive taxonomy (internal IDs, confidential categories)?**
A: Use environment-specific glossaries. Load different files for dev vs prod deployments.

**Q: Should synonyms include typos/misspellings?**
A: No. LLMs handle typos naturally. Only include genuine alternative terms.

---

**Last Updated:** December 16, 2025  
**See Also:** `IMPLEMENTATION_PLAN.md` Phase 3.1 for glossary creation workflow
