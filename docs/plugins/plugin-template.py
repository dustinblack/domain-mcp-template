"""
Plugin Template for Domain MCP Servers

TEMPLATE NOTE: This template uses "RHIVOS PerfScale" concepts (boot time metrics)
as an example. Replace with your domain (e.g., payment latency, API response time).
See docs/EXAMPLE_DOMAIN.md for mapping guidance.

This template demonstrates best practices for developing domain-specific plugins,
including proper use of shared utilities, error handling, and data extraction.

To use: Copy to src/domain/plugins/my_plugin.py and adapt for your domain.
"""

import logging
from typing import Any, Dict, List, Optional

# Import shared utilities (always use these instead of duplicating code)
from src.domain.models import MetricPoint
from src.domain.plugins import Plugin
from src.domain.utils.aggregation import group_by_statistic_type
from src.domain.utils.statistics import compute_statistics, detect_anomalies
from src.domain.utils.timestamps import parse_timestamp
from src.domain.utils.validation import is_valid_float, sanitize_float

# These are also available for use as needed:
# from src.domain.utils.aggregation import (
#     AggregationStrategy, MissingDataStrategy, aggregate_samples
# )
# from src.domain.utils.timestamps import calculate_time_delta_ms
# from src.domain.utils.units import TimeUnit, auto_scale_time, convert_time

logger = logging.getLogger(__name__)


class YourDomainPlugin(Plugin):
    """
    Plugin for extracting YOUR_DOMAIN metrics from Horreum datasets.

    Supports:
    - Label values extraction (fast path)
    - Raw dataset extraction (fallback path)
    - Multi-sample statistical analysis
    - Filtering by OS, run type, etc.

    Extracted Metrics:
    - your.metric.1 - Description of metric 1
    - your.metric.2 - Description of metric 2
    - your.metric.statistics.mean - Mean value from multi-sample data
    - your.metric.statistics.p95 - 95th percentile from multi-sample data
    """

    id = "your-domain-plugin"  # Unique identifier
    glossary: Dict[str, Dict[str, str]] = {}  # Domain-specific terminology
    kpis: List[str] = []  # Key performance indicators

    async def extract(
        self,
        json_body: object,
        refs: Dict[str, str],
        label_values: Optional[List[Any]] = None,
        os_filter: Optional[str] = None,
        run_type_filter: Optional[str] = None,
    ) -> List[MetricPoint]:
        """
        Extract metrics from dataset or label values.

        Parameters
        ----------
        json_body : dict
            Raw dataset JSON
        refs : dict
            References to related data
        label_values : list, optional
            Pre-computed label values (fast path)
        run_type_filter : str, optional
            Filter by run type (e.g., "nightly", "ci")
        os_filter : str, optional
            Filter by OS (e.g., "rhel", "autosd")

        Returns
        -------
        list of MetricPoint
            Extracted canonical metrics
        """
        # Prefer label values (fast path)
        if label_values:
            return await self.extract_from_label_values(
                label_values, os_filter, run_type_filter
            )

        # Fallback to dataset extraction
        return await self.extract_from_dataset(json_body, os_filter, run_type_filter)

    async def extract_from_label_values(
        self,
        label_values: List[Any],
        os_filter: Optional[str] = None,
        run_type_filter: Optional[str] = None,
    ) -> List[MetricPoint]:
        """
        Extract metrics from pre-computed label values (fast path).

        Best Practices:
        - Group by statistic type using group_by_statistic_type()
        - Validate all floats with is_valid_float() before creating MetricPoint
        - Parse timestamps with parse_timestamp()
        - Apply filters if provided
        """
        points: List[MetricPoint] = []

        # Group label values by statistic type (mean, p95, p99, etc.)
        grouped = group_by_statistic_type(label_values)

        # Process each statistic type
        for stat_type, items in grouped.items():
            for item in items:
                # Extract metadata
                run_start = item.get("start")
                if not run_start:
                    continue

                # Parse timestamp using shared utility
                timestamp = parse_timestamp(run_start)
                if not timestamp:
                    logger.warning(
                        "plugin.timestamp_parse_failed",
                        extra={"start": run_start, "plugin": self.id},
                    )
                    continue

                # Apply filters if provided
                if os_filter:
                    item_os = item.get("RHIVOS OS ID", "").lower()
                    if item_os != os_filter.lower():
                        continue

                if run_type_filter:
                    item_run_type = item.get("Run type", "").lower()
                    if item_run_type != run_type_filter.lower():
                        continue

                # Extract metric value
                metric_value = item.get("Your Metric Label")
                if metric_value is None:
                    continue

                # Convert to float and validate
                try:
                    value_float = float(metric_value)
                except (ValueError, TypeError):
                    logger.warning(
                        "plugin.value_parse_failed",
                        extra={"value": metric_value, "plugin": self.id},
                    )
                    continue

                # ✅ CRITICAL: Validate float before creating MetricPoint
                if not is_valid_float(value_float):
                    logger.warning(
                        "plugin.invalid_float_skipped",
                        extra={
                            "value": value_float,
                            "plugin": self.id,
                            "timestamp": str(timestamp),
                        },
                    )
                    continue

                # Extract dimensions for 3D matrix grouping
                dimensions = {
                    "statistic_type": stat_type,
                }

                # Add OS dimension if available
                os_id = item.get("RHIVOS OS ID")
                if os_id:
                    dimensions["os_id"] = os_id.lower()

                # Add mode dimension if available
                mode = item.get("RHIVOS Mode")
                if mode:
                    dimensions["mode"] = mode.lower()

                # Add target (platform/hardware) dimension if available
                target = item.get("RHIVOS Target")
                if target:
                    dimensions["target"] = target.lower()

                # Create MetricPoint
                points.append(
                    MetricPoint(
                        metric_id=f"your.metric.{stat_type}",
                        timestamp=timestamp,
                        value=value_float,
                        unit="your_unit",  # e.g., "milliseconds", "bytes", "percent"
                        dimensions=dimensions,
                        source="label_values",
                    )
                )

        logger.info(
            "plugin.extraction.complete",
            extra={
                "plugin": self.id,
                "points": len(points),
                "source": "label_values",
            },
        )

        return points

    async def extract_from_dataset(
        self,
        json_body: object,
        os_filter: Optional[str] = None,
        run_type_filter: Optional[str] = None,
    ) -> List[MetricPoint]:
        """
        Extract metrics from raw dataset (fallback path).

        Best Practices:
        - Detect multi-sample data and compute statistics with compute_statistics()
        - Use sanitize_float() with range constraints for data quality
        - Use calculate_time_delta_ms() for duration calculations
        - Handle missing data gracefully
        """
        points: List[MetricPoint] = []

        if not isinstance(json_body, dict):
            logger.warning(
                "plugin.invalid_dataset",
                extra={"type": type(json_body).__name__, "plugin": self.id},
            )
            return points

        # Extract metadata
        start_time_val = json_body.get("start")
        timestamp = parse_timestamp(start_time_val)
        if not timestamp:
            return points

        # Extract configuration (for dimensions and filtering)
        config = json_body.get("your_config", {})
        os_id = config.get("os_id", "").lower()
        run_type = config.get("run_type", "").lower()

        # Apply filters
        if os_filter and os_id != os_filter.lower():
            return points
        if run_type_filter and run_type != run_type_filter.lower():
            return points

        # Extract raw samples
        samples = json_body.get("samples", [])

        # Detect multi-sample data
        if len(samples) > 1:
            # Extract sample values
            sample_values = []
            for sample in samples:
                value = sample.get("metric_value")
                if value is None:
                    continue

                try:
                    value_float = float(value)
                except (ValueError, TypeError):
                    continue

                # Sanitize with range constraints
                clean_value = sanitize_float(
                    value_float, min_value=0.0, max_value=10000.0  # Adjust as needed
                )
                if clean_value is not None:
                    sample_values.append(clean_value)

            # Compute statistics on multi-sample data
            if sample_values:
                stats = compute_statistics(sample_values)
                if stats:
                    # Create MetricPoints for each statistic
                    dimensions = {"os_id": os_id, "mode": config.get("mode")}

                    metric_stats = {
                        "mean": stats.mean,
                        "median": stats.median,
                        "min": stats.min,
                        "max": stats.max,
                        "p95": stats.p95,
                        "p99": stats.p99,
                    }

                    for stat_name, stat_value in metric_stats.items():
                        if is_valid_float(stat_value):
                            points.append(
                                MetricPoint(
                                    metric_id=f"your.metric.{stat_name}",
                                    timestamp=timestamp,
                                    value=stat_value,
                                    unit="your_unit",
                                    dimensions={
                                        **dimensions,
                                        "statistic_type": stat_name,
                                    },
                                    source="dataset_multi_sample",
                                )
                            )

                    # Optionally detect anomalies
                    anomalies = detect_anomalies(
                        sample_values, method="iqr", threshold=1.5
                    )
                    if anomalies:
                        logger.info(
                            "plugin.anomalies_detected",
                            extra={
                                "plugin": self.id,
                                "count": len(anomalies),
                                "indices": anomalies,
                            },
                        )

        else:
            # Single sample - extract directly
            value = json_body.get("metric_value")
            if value is not None:
                try:
                    value_float = float(value)
                except (ValueError, TypeError):
                    return points

                if is_valid_float(value_float):
                    dimensions = {"os_id": os_id, "mode": config.get("mode")}

                    points.append(
                        MetricPoint(
                            metric_id="your.metric.value",
                            timestamp=timestamp,
                            value=value_float,
                            unit="your_unit",
                            dimensions=dimensions,
                            source="dataset_single_sample",
                        )
                    )

        logger.info(
            "plugin.extraction.complete",
            extra={
                "plugin": self.id,
                "points": len(points),
                "source": "dataset",
            },
        )

        return points


# Register the plugin
plugin_instance = YourDomainPlugin()
