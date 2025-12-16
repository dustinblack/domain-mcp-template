# Example Domain: RHIVOS PerfScale (Boot Time Analysis)

> **Purpose:** This document explains how the "RHIVOS PerfScale MCP" example domain is structured in this template. Use it as a reference when implementing your own domain.

## Overview

The template ships with a complete example: **RHIVOS PerfScale MCP**, a Domain MCP server for analyzing boot time performance metrics from Red Hat performance testing infrastructure.

**Why this example?** It demonstrates:
- Complex multi-dimensional data (OS, architecture, kernel version)
- Time-series performance metrics (boot time in seconds)
- Multiple KPIs (mean, p95, p99 percentiles)
- Integration with a specific Source MCP (Horreum)

## Domain: Boot Time Performance

### KPIs (Key Performance Indicators)

| KPI | Description | Unit | Aggregation |
|-----|-------------|------|-------------|
| `boot_time_seconds` | Time from GRUB to login prompt | seconds | mean, p95, p99 |
| `kernel_boot_time` | Time for kernel initialization | seconds | mean |
| `userspace_boot_time` | Time for userspace services to start | seconds | mean |

### Dimensions (Filters/Labels)

Users can filter and group metrics by:
- **os**: Operating system (e.g., `rhel`, `centos`, `fedora`)
- **arch**: CPU architecture (e.g., `x86_64`, `aarch64`)
- **kernel_version**: Kernel version string
- **run_type**: Test type (e.g., `nightly`, `pull-request`)

### Natural Language Queries

Example queries this domain supports:
- "Show me boot time for RHEL on x86_64 over the last week"
- "Compare kernel boot time between RHEL 9 and RHEL 10"
- "What's the p95 boot time for nightly runs?"

## Source MCP: Horreum

**Horreum** is a performance database and CI integration system used in Red Hat.

### Mapping to Source MCP Contract

| Contract Method | Horreum Mapping |
|-----------------|-----------------|
| `source_describe()` | Returns Horreum instance info |
| `tests_list()` | Lists available test schemas (e.g., `boot-time-verbose`) |
| `datasets_search()` | Fetches datasets filtered by test, time, labels |
| `label_values()` | Returns pre-computed label values (efficient for KPIs) |

### Data Shape

A Horreum dataset for boot time looks like:

```json
{
  "$schema": "urn:boot-time-verbose:1.0",
  "duration_ms": 45300,
  "measurements": [
    {"stage": "kernel", "duration_ms": 12000},
    {"stage": "userspace", "duration_ms": 33300}
  ],
  "labels": {
    "os": "rhel-9.5",
    "arch": "x86_64",
    "kernel_version": "5.14.0-503.el9"
  }
}
```

## Plugin: Boot Time Extraction

**File:** `src/domain/examples/horreum_boot_time.py`

### Extraction Logic

```python
def extract(json_body: dict, ...) -> List[MetricPoint]:
    # 1. Parse the Horreum dataset structure
    duration_ms = json_body.get("duration_ms")
    
    # 2. Convert to domain unit (seconds)
    boot_time_seconds = duration_ms / 1000.0
    
    # 3. Extract dimensions from labels
    labels = json_body.get("labels", {})
    dimensions = {
        "os": labels.get("os"),
        "arch": labels.get("arch"),
        "kernel_version": labels.get("kernel_version")
    }
    
    # 4. Create MetricPoint
    return [MetricPoint(
        timestamp=parse_timestamp(json_body.get("timestamp")),
        metric_name="boot_time_seconds",
        value=boot_time_seconds,
        unit="seconds",
        dimensions=dimensions
    )]
```

### Handling Edge Cases

- Missing `duration_ms`: Skip this dataset, log warning
- Unit conversion: Always convert milliseconds to seconds for consistency
- Invalid labels: Use `"unknown"` as default

## Glossary Resources

**Files:** `src/resources/glossary/boot_time_kpis.json`, `boot_time_dimensions.json`

These JSON files define domain terminology for LLM clients to understand:

```json
{
  "term": "boot_time_seconds",
  "definition": "Total time from bootloader (GRUB) to login prompt availability",
  "example_query": "Show me boot time for RHEL over the last week",
  "unit": "seconds",
  "aggregations": ["mean", "p95", "p99"]
}
```

## Fixtures for Testing

**Location:** `tests/fixtures/boot-time/`

- `horreum-v4-sample.json`: Real Horreum dataset response
- `run_120214_label_values.json`: Example of pre-computed label values
- `expected_extracted_metrics.json`: What the plugin should output

## Mapping to Your Domain

To adapt this example to your domain:

| PerfScale Concept | Your Domain Example |
|-------------------|---------------------|
| **Boot time** | Payment latency, API response time, etc. |
| **Dimensions:** os, arch, kernel_version | region, customer_tier, payment_method |
| **Source: Horreum** | Elasticsearch, Prometheus, PostgreSQL |
| **Unit: seconds** | milliseconds, bytes, count, percentage |
| **Plugin:** Parse Horreum dataset | Parse ES logs, Prometheus metrics, SQL rows |
| **Fixtures:** Horreum JSON | ES search response, Prometheus query result |

## Cleanup Checklist

When implementing your domain, remove/replace:

- [ ] `src/domain/examples/horreum_boot_time.py` (or adapt to your use case)
- [ ] `src/adapters/horreum.py` (if using a different source)
- [ ] `src/resources/glossary/boot_time_*.json` (replace with your KPIs)
- [ ] `tests/fixtures/boot-time/` (replace with your domain fixtures)
- [ ] Update `src/__version__.py` description
- [ ] Update all "RHIVOS PerfScale" references in docs to your project name

## Further Reading

- [Plugin Development Template](plugins/plugin-template.py)
- [Source MCP Contract](contracts/source-mcp-contract.md)
- [Domain Models](../src/domain/models.py) - `MetricPoint` structure

