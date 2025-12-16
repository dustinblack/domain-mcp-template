# Elasticsearch Logs Fixtures

Example Elasticsearch log documents and expected metric extraction for testing.

## Files

### `sample_documents.json`
Real-world-like Elasticsearch log documents showing the structure expected by `src/domain/examples/elasticsearch_logs.py`.

**Document Structure:**
- `@timestamp`: ISO 8601 timestamp
- `level` or `log.level`: Log level (INFO, WARN, ERROR, DEBUG)
- `service` or `service.name`: Service identifier
- `host` or `host.name`: Hostname
- `duration`, `latency`, `took`, or `*.duration_ms`: Duration fields in milliseconds

### `expected_metrics.json`
The MetricPoint objects that should be extracted from `sample_documents.json` by the Elasticsearch logs plugin.

**Extracted Metrics:**
- `log.count`: Always 1 per document (for aggregation)
- `log.duration_ms`: Extracted from duration/latency/took fields when present

## Usage

### Testing Your Elasticsearch Plugin

1. **Use as test input:**
```python
import json
from src.domain.examples.elasticsearch_logs import ElasticsearchLogsPlugin

with open('tests/fixtures/elasticsearch-logs/sample_documents.json') as f:
    data = json.load(f)

plugin = ElasticsearchLogsPlugin()
for doc in data['documents']:
    metrics = await plugin.extract(doc, refs={})
    # Assert metrics match expected output
```

2. **Create your own fixtures:**
- Copy `sample_documents.json` to `tests/fixtures/my_domain/`
- Replace with your actual Elasticsearch document structure
- Update `expected_metrics.json` with what your plugin should extract

## Adapting for Your Domain

If your Elasticsearch logs have different structure:

1. **Different field names:**
   - Update plugin to look for your fields
   - Document the mapping in your fixture README

2. **Additional metrics:**
   - Add more MetricPoint definitions
   - Update `expected_metrics.json` to include them

3. **Custom dimensions:**
   - Extract additional labels from your logs
   - Add to `dimensions` dict in expected output

## Example: Adapting for Application Logs

```python
# Your custom plugin might extract:
- error_rate: Count of ERROR level logs
- response_time_p95: 95th percentile of response times
- request_count: Total requests by endpoint
```

Create fixtures showing:
- Input: Your actual ES documents with these fields
- Expected: MetricPoint objects with your custom metrics

