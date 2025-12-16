"""Elasticsearch Logs plugin.

Extracts metrics from log documents returned by Elasticsearch.
This is a reference implementation showing how to process raw log data.

Metrics:
- log.count: 1 for every log entry (useful for aggregation)
- log.duration_ms: Extracted from 'duration', 'latency', or 'took' fields

Dimensions:
- level: Log level (INFO, ERROR, etc.)
- service: Service name
- host: Hostname
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models import MetricPoint
from ..utils.timestamps import parse_timestamp as _parse_timestamp
from ..utils.validation import is_valid_float as _is_valid_float

logger = logging.getLogger(__name__)


class ElasticsearchLogsPlugin:
    """Extracts metrics from Elasticsearch log documents."""

    id = "elasticsearch-logs"
    glossary: Dict[str, Dict[str, str]] = {}
    kpis: List[str] = []

    async def extract(
        self,
        json_body: object,
        refs: Dict[str, str],
        label_values: Optional[List[Any]] = None,
        os_filter: Optional[str] = None,
        run_type_filter: Optional[str] = None,
    ) -> List[MetricPoint]:
        """Extract metrics from a single log document."""
        _ = (refs, label_values, os_filter, run_type_filter)
        points: List[MetricPoint] = []

        if not isinstance(json_body, dict):
            return points

        # Get timestamp
        ts = _parse_timestamp(str(json_body.get("@timestamp"))) or datetime.now(
            timezone.utc
        )

        # Build dimensions
        dims: Dict[str, str] = {}

        # Common log fields
        if "level" in json_body:
            dims["level"] = str(json_body["level"]).upper()
        elif "log.level" in json_body:
            dims["level"] = str(json_body["log.level"]).upper()

        if "service" in json_body:
            dims["service"] = str(json_body["service"])
        elif "service.name" in json_body:
            dims["service"] = str(json_body["service.name"])

        if "host" in json_body:
            dims["host"] = str(json_body["host"])
        elif "host.name" in json_body:
            dims["host"] = str(json_body["host.name"])

        # Metric 1: Log Count (Always 1 per document)
        points.append(
            MetricPoint(
                metric_id="log.count",
                timestamp=ts,
                value=1.0,
                unit="count",
                dimensions=dims or None,
                source=self.id,
            )
        )

        # Metric 2: Duration (if present)
        # Check common duration fields
        duration = None
        for field in ["duration", "duration_ms", "latency", "latency_ms", "took"]:
            val = json_body.get(field)
            if isinstance(val, (int, float)):
                duration = float(val)
                break

        if duration is not None and _is_valid_float(duration):
            points.append(
                MetricPoint(
                    metric_id="log.duration_ms",
                    timestamp=ts,
                    value=duration,
                    unit="ms",
                    dimensions=dims or None,
                    source=self.id,
                )
            )

        return points


# Import register here
from ..plugins import register  # noqa: E402

register(ElasticsearchLogsPlugin())
