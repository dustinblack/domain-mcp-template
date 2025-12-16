"""
Domain Plugin Scaffold

TODO: Rename this file to match your domain (e.g., payment_latency.py, api_metrics.py)
TODO: Update the class name and docstring
TODO: Fill in the TODOs below with your domain-specific logic

Reference: docs/plugins/plugin-template.py for complete examples
"""

import logging
from typing import Any, Dict, List, Optional

from src.domain.models import MetricPoint
from src.domain.plugins import Plugin
from src.domain.utils.timestamps import parse_timestamp
from src.domain.utils.validation import is_valid_float, sanitize_float

logger = logging.getLogger(__name__)


class MyDomainPlugin(Plugin):
    """
    TODO: Update this docstring with your domain description
    
    Example:
    Plugin for extracting payment transaction latency metrics from Elasticsearch logs.
    
    Supports:
    - Extracting latency metrics from transaction logs
    - Filtering by region, payment method, customer tier
    - Computing percentiles (p50, p95, p99)
    
    Extracted Metrics:
    - payment_latency_ms: Time from request to completion (milliseconds)
    - success_rate: Percentage of successful transactions
    """

    id = "my-domain-plugin"  # TODO: Unique identifier for your plugin
    
    # TODO: Define your domain glossary (optional, can be loaded from JSON files)
    glossary: Dict[str, Dict[str, str]] = {
        "my_metric": {
            "definition": "TODO: What this metric measures",
            "unit": "TODO: Unit of measurement (e.g., seconds, count, bytes)",
            "example_query": "TODO: Natural language query using this metric"
        }
    }
    
    # TODO: List your Key Performance Indicators
    kpis: List[str] = [
        "my_metric_1",  # TODO: Replace with your KPI names
        "my_metric_2",
    ]

    async def extract(
        self,
        json_body: object,
        refs: Dict[str, str],
        label_values: Optional[List[Any]] = None,
        # TODO: Add your domain-specific filters here
        # region_filter: Optional[str] = None,
        # payment_method_filter: Optional[str] = None,
    ) -> List[MetricPoint]:
        """
        Extract metrics from source data.

        Parameters
        ----------
        json_body : dict
            Raw data from Source MCP (e.g., Elasticsearch document, Horreum dataset)
        refs : dict
            References to related data (test IDs, run IDs, etc.)
        label_values : list, optional
            Pre-computed values (if your source supports this optimization)
        
        TODO: Add your filter parameters to the docstring

        Returns
        -------
        list of MetricPoint
            Extracted canonical metrics
        """
        # PRODUCTION PATTERN: Initialize results list and validate input
        points: List[MetricPoint] = []
        
        # PRODUCTION PATTERN: Type validation at entry point
        # Production data often has unexpected types (lists, strings, None instead of dicts)
        if not isinstance(json_body, dict):
            logger.warning(
                "%s.extract.invalid_input_type",
                self.id,
                extra={
                    "type_received": type(json_body).__name__,
                    "expected": "dict",
                    "details": "Skipping non-dictionary input"
                }
            )
            return points  # Return empty list for invalid input
        
        # PRODUCTION PATTERN: Structured logging for observability
        # Log extraction start with context to help debug production issues
        logger.info(
            "%s.extract.start",
            self.id,
            extra={
                "document_keys": list(json_body.keys())[:10],  # First 10 keys only
                "ref_keys": list(refs.keys()) if refs else [],
                "has_label_values": bool(label_values),
                # "filter_applied": bool(locals().get("region_filter")),  # Uncomment if you add filters
            }
        )
        
        try:
            # TODO: Implement your extraction logic here
            # This is where you map source data fields to MetricPoint objects
            # TODO: Step 1 - Extract the timestamp from your source data
            # 
            # EXAMPLES BY DATA SOURCE:
            # 
            # Elasticsearch (common field names):
            #   timestamp_str = json_body.get("@timestamp")  # Most common
            #   # Or: json_body.get("timestamp")
            #   # Or: json_body.get("event.timestamp")
            #   timestamp = parse_timestamp(timestamp_str) if timestamp_str else None
            # 
            # Elasticsearch (nested structure):
            #   event = json_body.get("event", {})
            #   timestamp_str = event.get("created")
            #   timestamp = parse_timestamp(timestamp_str) if timestamp_str else None
            #
            # Horreum (from refs):
            #   timestamp_str = refs.get("start_time")
            #   timestamp = parse_timestamp(timestamp_str) if timestamp_str else None
            #
            # Database/CSV (epoch milliseconds):
            #   epoch_ms = json_body.get("timestamp_ms")
            #   timestamp = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
            #
            # VALIDATION:
            #   if not timestamp:
            #       logger.warning("Missing timestamp in document, skipping")
            #       return []  # Skip documents without timestamps
            
            timestamp = None  # TODO: Replace with actual timestamp extraction
            
            # TODO: Step 2 - Extract the metric value from your source data
            # 
            # EXAMPLES BY DATA STRUCTURE:
            # 
            # Flat structure (simple field):
            #   raw_value = json_body.get("latency_ms")
            #
            # Nested structure:
            #   timing = json_body.get("timing", {})
            #   raw_value = timing.get("page_load_ms")
            #
            # Multiple fields (need to pick one):
            #   # Try multiple field names
            #   raw_value = (json_body.get("duration_ms") or 
            #                json_body.get("elapsed_ms") or 
            #                json_body.get("took"))
            #
            # WITH UNIT CONVERSION:
            #   raw_ms = json_body.get("duration_ms")
            #   value = raw_ms / 1000.0  # Convert milliseconds → seconds
            #
            # WITH VALIDATION (RECOMMENDED):
            #   raw_value = json_body.get("latency_ms")
            #   if raw_value and is_valid_float(raw_value):
            #       value = sanitize_float(raw_value)
            #   else:
            #       logger.warning("Invalid metric value: %s", raw_value)
            #       return []  # Skip invalid data
            #
            # COMPUTED VALUE (from multiple fields):
            #   start = json_body.get("start_time_ms")
            #   end = json_body.get("end_time_ms")
            #   if start and end:
            #       value = float(end - start)
            
            value = None  # TODO: Replace with actual value extraction
            
            # TODO: Step 2b - Handle multi-sample data (OPTIONAL - for performance testing)
            # 
            # WHEN TO USE:
            # - Your data has multiple samples per test run (e.g., 10 boot times, 100 API calls)
            # - You need statistical analysis (mean, p95, p99, standard deviation)
            # - Common in performance/load testing where tests run N times
            #
            # SKIP THIS if your data has only one measurement per document.
            #
            # DETECTION PATTERN - Array of values in a single field:
            #   samples = json_body.get("measurements")  # e.g., [12.3, 12.5, 12.1, 12.8, ...]
            #   if isinstance(samples, list) and len(samples) > 1:
            #       # Multi-sample dataset detected
            #       if all(isinstance(x, (int, float)) for x in samples):
            #           from src.domain.utils.statistics import compute_statistics
            #           
            #           # Compute statistics across all samples
            #           stats = compute_statistics([float(x) for x in samples])
            #           # Returns: {"mean": 12.3, "median": 12.4, "p95": 12.8, "p99": 12.9,
            #           #           "std_dev": 0.4, "cv": 0.03, "min": 12.1, "max": 12.9}
            #           
            #           # Create MetricPoints for each statistic
            #           for stat_name, stat_value in stats.items():
            #               if is_valid_float(stat_value):  # Skip inf/nan
            #                   points.append(MetricPoint(
            #                       timestamp=timestamp,
            #                       metric_name=f"my_metric.{stat_name}",  # e.g., "boot_time.p95"
            #                       value=float(stat_value),
            #                       unit="ms",
            #                       dimensions=dimensions
            #                   ))
            #           
            #           return points  # Early return - we've extracted all metrics
            #
            # DETECTION PATTERN - Multiple documents with same test_id:
            #   # If your source returns multiple docs per test, you'll need to:
            #   # 1. Group by test_id in the calling orchestrator code
            #   # 2. Pass all values to this plugin
            #   # 3. Compute stats here
            #   test_id = refs.get("test_id")
            #   all_values = [doc["value"] for doc in grouped_docs]
            #   stats = compute_statistics(all_values)
            #
            # STATISTICAL METRICS NAMING CONVENTION:
            # ✅ GOOD (consistent with production patterns):
            #   - Primary metric with mean: "boot_time" or "boot_time.mean"
            #   - Percentiles: "boot_time.p50", "boot_time.p75", "boot_time.p95", "boot_time.p99"
            #   - Variability: "boot_time.std_dev", "boot_time.cv" (coefficient of variation)
            #   - Range: "boot_time.min", "boot_time.max"
            #
            # ❌ AVOID:
            #   - "boot_time_p95" (underscore, hard to parse)
            #   - "boot_time-p95" (hyphen, inconsistent)
            #   - "p95_boot_time" (statistic first, harder to group)
            #
            # EXAMPLE OUTPUT - Single test run with 10 samples:
            # Input: {"measurements": [12.1, 12.3, 12.5, 12.2, 12.4, 12.6, 12.3, 12.7, 12.5, 12.4]}
            # Output: [
            #   MetricPoint(metric_name="boot_time.mean", value=12.4, ...),
            #   MetricPoint(metric_name="boot_time.p95", value=12.7, ...),
            #   MetricPoint(metric_name="boot_time.p99", value=12.7, ...),
            #   MetricPoint(metric_name="boot_time.std_dev", value=0.17, ...),
            # ]
            
            # TODO: Step 3 - Extract dimensions (labels/tags) from your source data
            # 
            # EXAMPLES BY DATA STRUCTURE:
            # 
            # Flat structure:
            #   dimensions = {
            #       "region": json_body.get("region", "unknown"),
            #       "device_type": json_body.get("device_type", "unknown"),
            #   }
            #
            # Nested structure:
            #   user = json_body.get("user", {})
            #   dimensions = {
            #       "region": user.get("region", "unknown"),
            #       "tier": user.get("tier", "unknown"),
            #       "device": user.get("device_type", "unknown"),
            #   }
            #
            # Multiple nested objects:
            #   user = json_body.get("user", {})
            #   request = json_body.get("request", {})
            #   dimensions = {
            #       "region": user.get("region", "unknown"),
            #       "method": request.get("method", "unknown"),
            #       "status": str(request.get("status_code", "unknown")),
            #   }
            #
            # WITH TRANSFORMATION:
            #   dimensions = {
            #       "region": json_body.get("region", "unknown"),
            #       "browser": json_body.get("user_agent", "unknown")[:50],  # Truncate long values
            #       "success": "true" if json_body.get("status_code") == 200 else "false",
            #   }
            #
            # PRODUCTION PATTERN - Robust extraction with type checking:
            #   dimensions = {}
            #   
            #   # Extract nested config object
            #   config = json_body.get("config", {})
            #   if isinstance(config, dict):  # ALWAYS check type before accessing nested fields
            #       # Extract os_id with validation
            #       os_id = config.get("os_id")
            #       if isinstance(os_id, str) and os_id:  # Verify it's a non-empty string
            #           dimensions["os_id"] = os_id
            #       
            #       # Extract mode with validation
            #       mode = config.get("mode")
            #       if isinstance(mode, str) and mode:
            #           dimensions["mode"] = mode
            #       
            #       # Extract numeric dimension (convert to string)
            #       cpu_cores = config.get("cpu_cores")
            #       if isinstance(cpu_cores, int):
            #           dimensions["cpu_cores"] = str(cpu_cores)  # Dimensions must be strings
            #   
            #   # Apply filters with dimension validation
            #   # if os_filter:
            #   #     extracted_os = dimensions.get("os_id")
            #   #     if not extracted_os:
            #   #         logger.debug(
            #   #             "%s.extract.missing_dimension",
            #   #             self.id,
            #   #             extra={
            #   #                 "filter": "os_filter",
            #   #                 "filter_value": os_filter,
            #   #                 "dimension_found": None,
            #   #                 "action": "skipping_document"
            #   #             }
            #   #         )
            #   #         return points  # Skip if filtered dimension is missing
            #   #     if extracted_os.lower() != os_filter.lower():
            #   #         return points  # Doesn't match filter
            #
            # WHY TYPE CHECKING IS CRITICAL:
            # - Source data may have wrong types (int instead of str, null values, arrays)
            # - Missing type checks cause crashes in dimension comparison/filtering
            # - Better to skip one bad document than crash the entire query
            # - Dimensions MUST be strings for proper grouping/filtering
            #
            # ⚠️ CARDINALITY WARNING:
            #   # BAD - creates millions of unique combinations:
            #   # dimensions = {"user_id": json_body.get("user_id")}
            #   # dimensions = {"url": json_body.get("full_url")}
            #   # dimensions = {"transaction_id": json_body.get("tx_id")}
            #   
            #   # GOOD - groups into categories (keep under 50-500 unique values):
            #   dimensions = {
            #       "endpoint_category": self._categorize_endpoint(json_body.get("url")),
            #       "user_tier": json_body.get("user_tier"),  # e.g., "free", "pro", "enterprise"
            #       "region": json_body.get("region"),  # e.g., 5-10 regions
            #   }
            
            dimensions = {}  # TODO: Replace with actual dimension extraction
            
            # TODO: Step 4 - Apply any filters if specified
            # 
            # EXAMPLES:
            #
            # Single filter:
            #   if region_filter and dimensions.get("region") != region_filter:
            #       return []  # Skip this data point
            #
            # Multiple filters (all must match):
            #   if region_filter and dimensions.get("region") != region_filter:
            #       return []
            #   if browser_filter and dimensions.get("browser") != browser_filter:
            #       return []
            #
            # Event type filtering (common pattern):
            #   if json_body.get("event_type") != "page_load":
            #       return []  # This plugin only handles page_load events
            #
            # NOTE: Filters should ideally be applied in the adapter (ES Query DSL, SQL WHERE)
            #       for performance. Plugin-level filtering is a fallback.
            
            # TODO: Step 5 - Create MetricPoint(s) and add to results
            # 
            # SINGLE METRIC:
            #   if timestamp and value is not None:
            #       points.append(MetricPoint(
            #           timestamp=timestamp,
            #           metric_name="page_load_time",
            #           value=value,
            #           unit="ms",
            #           dimensions=dimensions
            #       ))
            #
            # MULTIPLE METRICS from same document:
            #   timing = json_body.get("timing", {})
            #   
            #   # Page load time
            #   if timing.get("page_load_ms"):
            #       points.append(MetricPoint(
            #           timestamp=timestamp,
            #           metric_name="page_load_time",
            #           value=float(timing["page_load_ms"]),
            #           unit="ms",
            #           dimensions=dimensions
            #       ))
            #   
            #   # TTFB
            #   if timing.get("ttfb_ms"):
            #       points.append(MetricPoint(
            #           timestamp=timestamp,
            #           metric_name="ttfb",
            #           value=float(timing["ttfb_ms"]),
            #           unit="ms",
            #           dimensions=dimensions
            #       ))
            #
            # ERROR HANDLING:
            #   if timestamp and value is not None:
            #       points.append(MetricPoint(...))
            #   else:
            #       logger.warning("Skipping document due to missing data: timestamp=%s, value=%s",
            #                      timestamp, value)
            
            logger.warning("TODO: Implement extraction logic in %s", self.__class__.__name__)
            
        except Exception as e:
            logger.error(
                "%s.extract.error",
                self.id,
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "partial_results": len(points),
                },
                exc_info=True
            )
            # PRODUCTION PATTERN: Don't crash on errors - return partial results
            # This allows other documents to be processed even if one fails
        
        # PRODUCTION PATTERN: Log extraction results for observability
        logger.info(
            "%s.extract.complete",
            self.id,
            extra={
                "metrics_extracted": len(points),
                "metric_ids": [p.metric_name for p in points[:5]],  # First 5 metric names
                "dimensions": points[0].dimensions if points else None,
                "timestamp": points[0].timestamp.isoformat() if points else None,
            }
        )
        
        return points

    # TODO: Add helper methods as needed
    # Example:
    # def _convert_units(self, value: float, source_unit: str) -> float:
    #     """Convert value from source unit to canonical unit."""
    #     if source_unit == "ms" and self.target_unit == "seconds":
    #         return value / 1000.0
    #     return value


# TODO: When ready, register your plugin in src/domain/plugins/__init__.py
# Example:
# from src.domain.plugins.my_domain import MyDomainPlugin
# __all__ = ["MyDomainPlugin"]

