"""BootTime plugin compatible with multiple boot-time dataset formats.

This plugin extracts canonical KPIs from:
- RHIVOS local collector format (tests/fixtures/boot-time/successful-boot.json)
- Horreum v4/v5/v6 boot-time verbose schema

Extracted KPIs:
- boot.time.total_ms (PRIMARY KPI - total boot time)

Boot Phase Durations:
- boot.phase.kernel_pre_timer_ms (early kernel init, before timer)
- boot.phase.kernel_ms (kernel init, post-timer)
- boot.phase.initrd_ms (initial RAM disk execution)
- boot.phase.switchroot_ms (transition to actual root filesystem)
- boot.phase.system_init_ms (systemd/userspace initialization)

Critical Timestamp KPIs:
- boot.timestamp.early_service_ms (first critical service active)
- boot.timestamp.start_kmod_load_ms (kernel module loading begins)
- boot.timestamp.first_service_ms (first systemd service activated)
- boot.timestamp.network_online_ms (network connectivity established)

Dimensions (when available - 3D Result Matrix):
- os_id: Operating system (rhel, autosd, fedora, centos)
  - From label: "RHIVOS OS ID"
  - From dataset: .rhivos_config.os_id or .system_config.os_id
- mode: Image type (package, container, OSTree)
  - From label: "RHIVOS Mode"
  - From dataset: .rhivos_config.mode
- target: Hardware platform (qemu, intel-nuc, raspberry-pi, orin, ridesx4)
  - From label: "RHIVOS Target"
  - From dataset: .rhivos_config.image_target

Note: Datasets use field names inconsistently. The label values use correct
terminology and provide all three dimensions for the 3D result matrix.

Data Access Efficiency:
The plugin supports two extraction paths with automatic preference:
1. PREFERRED: Label values (Phase 2.5) - Pre-transformed metrics from Horreum
   - Faster: No dataset parsing required
   - Smaller: Only metrics, not full dataset JSON
   - Server-filtered: Horreum filters before returning data
2. FALLBACK: Raw datasets - Full dataset JSON parsing
   - Used when label values unavailable or incomplete
   - Slower but comprehensive

The extract() method automatically uses label values when provided, falling
back to dataset parsing when necessary. This ensures optimal performance
while maintaining compatibility.

See docs/domain-glossary.md for complete domain knowledge reference.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models import MetricPoint
from ..utils.statistics import compute_statistics
from ..utils.timestamps import parse_timestamp as _parse_timestamp
from ..utils.validation import is_valid_float as _is_valid_float

logger = logging.getLogger(__name__)


class BootTimePlugin:
    """Extracts boot-time KPIs from boot-time datasets.

    Supports both RHIVOS local fixtures and Horreum v4 boot-time verbose
    datasets. The extractor is conservative and only emits metrics when the
    relevant fields are confidently identified.
    """

    id = "boot-time-verbose"

    glossary = {
        # Primary KPI
        "boot.time.total_ms": {
            "description": "Total boot time (mean for multi-sample)",
            "unit": "ms",
        },
        # Statistical metrics (multi-sample datasets)
        "boot.time.total_ms.mean": {
            "description": "Mean boot time across samples",
            "unit": "ms",
        },
        "boot.time.total_ms.median": {
            "description": "Median boot time across samples",
            "unit": "ms",
        },
        "boot.time.total_ms.p95": {
            "description": "95th percentile boot time",
            "unit": "ms",
        },
        "boot.time.total_ms.p99": {
            "description": "99th percentile boot time",
            "unit": "ms",
        },
        "boot.time.total_ms.std_dev": {
            "description": "Standard deviation of boot time",
            "unit": "ms",
        },
        "boot.time.total_ms.cv": {
            "description": (
                "Coefficient of variance " "(normalized variability = std_dev/mean)"
            ),
            "unit": "ratio",
        },
        "boot.time.total_ms.min": {
            "description": "Minimum boot time across samples",
            "unit": "ms",
        },
        "boot.time.total_ms.max": {
            "description": "Maximum boot time across samples",
            "unit": "ms",
        },
        # Boot Phase Durations
        "boot.phase.kernel_pre_timer_ms": {
            "description": "Kernel initialization before timer subsystem",
            "unit": "ms",
        },
        "boot.phase.kernel_ms": {
            "description": "Kernel initialization after timer subsystem",
            "unit": "ms",
        },
        "boot.phase.initrd_ms": {
            "description": "Initial RAM disk execution duration",
            "unit": "ms",
        },
        "boot.phase.switchroot_ms": {
            "description": "Transition from initrd to actual root filesystem",
            "unit": "ms",
        },
        "boot.phase.system_init_ms": {
            "description": "System/userspace initialization (systemd)",
            "unit": "ms",
        },
        # Critical Timestamp KPIs
        "boot.timestamp.early_service_ms": {
            "description": "First critical service becomes active",
            "unit": "ms",
        },
        "boot.timestamp.start_kmod_load_ms": {
            "description": "Kernel module loading begins",
            "unit": "ms",
        },
        "boot.timestamp.first_service_ms": {
            "description": "First systemd service activated",
            "unit": "ms",
        },
        "boot.timestamp.network_online_ms": {
            "description": "Network connectivity established",
            "unit": "ms",
        },
    }

    kpis = [
        "boot.time.total_ms",  # PRIMARY KPI
        # Phase durations
        "boot.phase.kernel_pre_timer_ms",
        "boot.phase.kernel_ms",
        "boot.phase.initrd_ms",
        "boot.phase.switchroot_ms",
        "boot.phase.system_init_ms",
        # Critical timestamps
        "boot.timestamp.early_service_ms",
        "boot.timestamp.start_kmod_load_ms",
        "boot.timestamp.first_service_ms",
        "boot.timestamp.network_online_ms",
    ]

    async def extract(
        self,
        json_body: object,
        refs: Dict[str, str],
        label_values: Optional[List[Any]] = None,
        os_filter: Optional[str] = None,
        run_type_filter: Optional[str] = None,
    ) -> List[MetricPoint]:
        """Extract canonical metric points from boot-time dataset or label values.

        Parameters
        ----------
        json_body: object
            Raw dataset JSON content (usually a dict)
        refs: Dict[str, str]
            Contextual references (e.g., runId, datasetId). Unused for now.
        label_values: Optional[List[Any]]
            Optional pre-transformed label values from source (Phase 2.5).
            If provided, prefer extracting from these.
        run_type_filter: Optional[str]
            Optional run type filter (e.g., "nightly", "ci"). If provided,
            performs client-side filtering for legacy data where "nightly"
            appears in "Test Description" label.

        Returns
        -------
        List[MetricPoint]
            A list of extracted metric points. Empty if nothing recognized.
        """
        _ = refs
        points: List[MetricPoint] = []

        # Log extraction start with filters
        logger.info(
            "boot_time.extract.start",
            extra={
                "has_label_values": bool(label_values),
                "run_type_filter": run_type_filter,
                "os_filter": os_filter,
                "json_body_keys": (
                    list(json_body.keys()) if isinstance(json_body, dict) else None
                ),
            },
        )

        # Phase 2.5: Try label values first if provided
        if label_values:
            logger.info(
                "boot_time.extract.trying_label_values",
                extra={"label_value_count": len(label_values)},
            )
            lv_points = await self.extract_from_label_values(
                label_values,
                run_type_filter=run_type_filter,
                os_filter=os_filter,
            )
            if lv_points:
                logger.info(
                    "boot_time.extract.label_values_success",
                    extra={
                        "metric_count": len(lv_points),
                        "metrics": [p.metric_id for p in lv_points],
                    },
                )
                return lv_points
            else:
                logger.warning(
                    "boot_time.extract.label_values_empty",
                    extra={"details": "Label values provided but no metrics extracted"},
                )

        # Fallback to dataset JSON parsing
        logger.info("boot_time.extract.trying_dataset_parsing")
        if not isinstance(json_body, dict):
            logger.warning("boot_time.extract.dataset_not_dict")
            return points

        # Check for multi-sample data first
        boot_time_field = json_body.get("boot_time")
        if isinstance(boot_time_field, list) and boot_time_field:
            logger.info(
                "boot_time.extract.detected_multi_sample",
                extra={"sample_count": len(boot_time_field)},
            )
            if all(isinstance(x, (int, float)) for x in boot_time_field):
                # Multi-sample dataset detected
                samples = [float(x) for x in boot_time_field]
                stats = self._compute_statistics(samples)
                if stats:
                    # Extract dimensions
                    dims: Dict[str, str] = {}
                    rhcfg = json_body.get("rhivos_config")
                    if isinstance(rhcfg, dict):
                        os_id = rhcfg.get("os_id")
                        mode = rhcfg.get("image_target") or rhcfg.get("mode")
                        if isinstance(os_id, str):
                            dims["os_id"] = os_id
                            # Apply OS filtering if requested
                            if os_filter and os_id.lower() != os_filter.lower():
                                return points  # Skip this dataset
                        if isinstance(mode, str):
                            dims["mode"] = mode

                    ts = datetime.now(timezone.utc)

                    # Create MetricPoints for each statistic (skip invalid floats)
                    for stat_name, stat_value in stats.items():
                        float_val = float(stat_value)
                        if _is_valid_float(float_val):
                            points.append(
                                MetricPoint(
                                    metric_id=f"boot.time.total_ms.{stat_name}",
                                    timestamp=ts,
                                    value=float_val,
                                    unit="ms",
                                    dimensions=dims or None,
                                    source=self.id,
                                )
                            )
                        else:
                            logger.warning(
                                "boot_time.invalid_float_skipped",
                                extra={
                                    "metric_id": f"boot.time.total_ms.{stat_name}",
                                    "value": float_val,
                                    "details": "Float value is inf or nan, skipping",
                                },
                            )

                    # Also add the mean as the primary metric
                    # (for backwards compatibility)
                    if "mean" in stats:
                        mean_val = float(stats["mean"])
                        if _is_valid_float(mean_val):
                            points.append(
                                MetricPoint(
                                    metric_id="boot.time.total_ms",
                                    timestamp=ts,
                                    value=mean_val,
                                    unit="ms",
                                    dimensions=dims or None,
                                    source=self.id,
                                )
                            )
                        else:
                            logger.warning(
                                "boot_time.invalid_float_skipped",
                                extra={
                                    "metric_id": "boot.time.total_ms",
                                    "value": mean_val,
                                    "details": "Float value is inf or nan, skipping",
                                },
                            )
                    return points

        # Single-sample data: Try RHIVOS local fixture format first
        logger.info("boot_time.extract.trying_rhivos_local")
        extracted_points = self._extract_rhivos_local(json_body, os_filter=os_filter)
        if not extracted_points:
            logger.info("boot_time.extract.trying_horreum_v4")
            # Try Horreum v4 boot-time verbose schema
            extracted_points = self._extract_horreum_v4(json_body, os_filter=os_filter)

        if extracted_points:
            logger.info(
                "boot_time.extract.dataset_parsing_success",
                extra={
                    "metric_count": len(extracted_points),
                    "metrics": [p.metric_id for p in extracted_points],
                },
            )
            points.extend(extracted_points)
        else:
            logger.warning(
                "boot_time.extract.no_metrics_extracted",
                extra={"details": "No recognized format found in dataset"},
            )

        return points

    async def extract_from_label_values(
        self,
        items: List[Dict[str, Any]],
        run_type_filter: Optional[str] = None,
        os_filter: Optional[str] = None,
    ) -> List[MetricPoint]:
        """Extract KPIs from label values bundles (preferred path when available).

        IMPORTANT: Total boot time is CALCULATED by summing boot phases, not extracted
        from a label. Missing or non-numeric phase values are treated as 0 for
        calculations and reported as "not available" when used directly, and
        missing phases should be tracked and reported.

        Parameters
        ----------
        items: List[Dict[str, Any]]
            Each item should contain a ``values`` list with dicts holding
            ``name`` and ``value`` keys, and optional ``start``/``stop``
            timestamps. This shape mirrors the ExportedLabelValues model but is
            intentionally dict-typed to avoid coupling plugins to schema types.
        run_type_filter: Optional[str]
            Optional run type filter (e.g., "nightly", "ci"). If provided,
            performs client-side filtering for legacy data where the run type
            appears in "Test Description" label.

        Returns
        -------
        List[MetricPoint]
            Extracted metric points with boot phases and calculated total.
        """
        points: List[MetricPoint] = []
        if not isinstance(items, list):
            return points

        logger.info(
            "boot_time.extract_from_label_values.start",
            extra={
                "item_count": len(items),
                "run_type_filter": run_type_filter,
                "os_filter": os_filter,
            },
        )

        # Helper function to normalize label names for flexible matching
        def normalize_label_name(name: str) -> str:
            """Normalize: lowercase, remove special chars, collapse spaces."""
            return " ".join(name.lower().replace("-", " ").split())

        # Helper function to determine if label represents a duration vs timestamp
        def is_duration(name: str) -> bool:
            """Check if label name indicates a duration measurement."""
            norm_name = normalize_label_name(name)
            # Duration indicators
            return (
                any(
                    word in norm_name
                    for word in ["duration", "time", "ms", "latency", "delay"]
                )
                and "timestamp" not in norm_name
            )

        def is_timestamp(name: str) -> bool:
            """Check if label name indicates a timestamp measurement."""
            norm_name = normalize_label_name(name)
            return "timestamp" in norm_name or "ts" in norm_name

        def extract_statistic_type(name: str) -> Optional[str]:
            """Extract statistic type from label name.

            Returns:
                'average' if label contains "Average" or "average"
                'confidence' if label contains "Confidence" or "confidence"
                None if no statistic type detected
            """
            norm_name = normalize_label_name(name)
            if "average" in norm_name:
                return "average"
            elif "confidence" in norm_name:
                return "confidence"
            # Could extend for other types: min, max, median, etc.
            return None

        # Helper function to match label name to canonical metric ID
        def match_label_to_metric(name: str) -> Optional[str]:
            """Match a label name to a canonical metric ID using flexible patterns."""
            norm_name = normalize_label_name(name)

            # Boot phases - match any label with "boot" and duration indicators
            if ("boot" in norm_name or name.startswith("BOOT")) and is_duration(name):
                # Identify specific phase by keywords
                if "kernel" in norm_name and ("pre" in norm_name or "1" in name):
                    return "boot.phase.kernel_pre_timer_ms"
                elif "kernel" in norm_name and ("post" in norm_name or "2" in name):
                    return "boot.phase.kernel_ms"
                elif "initrd" in norm_name or "initramfs" in norm_name or "3" in name:
                    return "boot.phase.initrd_ms"
                elif (
                    "switchroot" in norm_name
                    or ("switch" in norm_name and "root" in norm_name)
                    or "4" in name
                ):
                    return "boot.phase.switchroot_ms"
                elif (
                    "systeminit" in norm_name.replace(" ", "")
                    or ("system" in norm_name and "init" in norm_name)
                    or "userspace" in norm_name
                    or "0" in name
                ):
                    return "boot.phase.system_init_ms"
                # If we can't determine specific phase but it's clearly a boot duration,
                # default to total boot time
                elif "total" in norm_name or norm_name in [
                    "boot time",
                    "boot",
                    "boot_time",
                ]:
                    return "boot.time.total_ms"

            # KPI timestamps - match any label with "KPI" and timestamp indicators
            elif "kpi" in norm_name and is_timestamp(name):
                # Identify specific KPI by keywords
                if "early" in norm_name and "service" in norm_name:
                    return "boot.timestamp.early_service_ms"
                elif "kmod" in norm_name or (
                    "module" in norm_name and "load" in norm_name
                ):
                    return "boot.timestamp.start_kmod_load_ms"
                elif "first" in norm_name and (
                    "service" in norm_name or "link" in norm_name
                ):
                    return "boot.timestamp.first_service_ms"
                elif "network" in norm_name or (
                    "link" in norm_name and "up" in norm_name
                ):
                    return "boot.timestamp.network_online_ms"

            # Total boot time - exact matches for backward compatibility
            elif name in {
                "boot.time.total_ms",
                "boot.total_ms",
                "boot_time_total_ms",
                "Boot Time",
                "boot_time",
            }:
                return "boot.time.total_ms"

            return None

        filtered_by_run_type = 0
        filtered_by_os = 0
        items_processed = 0
        labels_found = []
        skipped_labels = []  # Track labels with invalid/missing values

        for item in items:
            if not isinstance(item, dict):
                continue

            items_processed += 1

            # Client-side filtering for run type
            if run_type_filter:
                # Check if "Run type" label exists (modern data)
                run_type_label = None
                test_desc_label = None
                values_list = item.get("values")
                if isinstance(values_list, list):
                    for lv in values_list:
                        if isinstance(lv, dict):
                            name = lv.get("name")
                            value = lv.get("value")
                            if name == "Run type":
                                run_type_label = value
                            elif name == "Test Description":
                                test_desc_label = value

                # Check "Run type" label first (modern data, exact match)
                if run_type_label is not None:
                    # Modern data: Check for exact match with Run type label
                    if run_type_label.lower() != run_type_filter.lower():
                        # Run type doesn't match - skip this item
                        filtered_by_run_type += 1
                        continue
                elif test_desc_label:
                    # Legacy data: Check if run_type_filter appears in Test Description
                    if (
                        not isinstance(test_desc_label, str)
                        or run_type_filter.lower() not in test_desc_label.lower()
                    ):
                        # Test Description doesn't contain run type - skip this item
                        filtered_by_run_type += 1
                        continue
                # If neither Run type nor Test Description exists, don't filter
                # (can't determine run type)

            # Client-side filtering for OS
            if os_filter:
                # Check if "RHIVOS OS ID" label exists
                os_id_label = None
                values_list = item.get("values")
                if isinstance(values_list, list):
                    for lv in values_list:
                        if isinstance(lv, dict):
                            name = lv.get("name")
                            value = lv.get("value")
                            if name == "RHIVOS OS ID":
                                os_id_label = value
                                break

                # Filter by OS ID (exact match, case-insensitive)
                if os_id_label is not None:
                    if os_id_label.lower() != os_filter.lower():
                        # OS doesn't match - skip this item
                        filtered_by_os += 1
                        continue
                # If no OS ID label exists, don't filter
                # (can't determine OS)

            values = item.get("values")
            # Handle both dict (from Horreum API direct) and list (from MCP contract)
            # Defensive: Horreum MCP fix deployed 2025-10-16, but keep both paths
            # until verified in production
            values_items: List[tuple]
            if isinstance(values, dict):
                # Dict format: {"RHIVOS OS ID": "autosd", ...}
                values_items = list(values.items())
            elif isinstance(values, list):
                # List format: [{"name": "RHIVOS OS ID", "value": "autosd"}, ...]
                values_items = [
                    (lv.get("name"), lv.get("value"))
                    for lv in values
                    if isinstance(lv, dict)
                ]
            else:
                continue

            # Extract dimension values from labels (os_id, mode, target)
            # AND metadata fields (release, image_name, samples, user, build)
            # These apply to all metrics in this item
            item_os_id = None
            item_mode = None
            item_target = None
            item_release = None
            item_image_name = None
            item_samples = None
            item_user = None
            item_build = None
            for name, value in values_items:
                if name == "RHIVOS OS ID" and isinstance(value, str):
                    item_os_id = value.lower()
                elif name == "RHIVOS Mode" and isinstance(value, str):
                    item_mode = value.lower()
                elif name == "RHIVOS Target" and isinstance(value, str):
                    item_target = value.lower()
                elif name == "RHIVOS Release" and isinstance(value, str):
                    item_release = value
                elif name == "RHIVOS image name" and isinstance(value, str):
                    item_image_name = value
                elif name == "Number of Samples" and isinstance(
                    value, (int, float, str)
                ):
                    # Convert to int if it's a string or float
                    try:
                        item_samples = int(value)
                    except (ValueError, TypeError):
                        pass
                elif name == "User" and isinstance(value, str):
                    item_user = value
                elif name == "RHIVOS Build" and isinstance(value, str):
                    item_build = value

            # Timestamp: prefer stop, else start, else now
            ts = item.get("stop") or item.get("start")
            if isinstance(ts, str):
                ts_dt = _parse_timestamp(ts)
            elif isinstance(ts, datetime):
                ts_dt = ts
            else:
                ts_dt = None

            # PHASE 1: Collect all label values into a structured dict
            # We need to group by statistic_type (average/confidence) to calculate
            # total boot time separately for each statistic type
            phase_data_by_stat_type: Dict[str, Dict[str, float]] = {}
            missing_phases_by_stat_type: Dict[str, List[str]] = {}
            kpi_data: List[tuple[str, float, str]] = []

            for lv in values:
                if not isinstance(lv, dict):
                    continue
                name = lv.get("name")
                if not isinstance(name, str):
                    continue

                # Track all label names we encounter
                if name not in labels_found:
                    labels_found.append(name)

                # Match label name to canonical metric ID
                metric_id = match_label_to_metric(name)
                if not metric_id:
                    logger.debug(
                        "boot_time.unrecognized_label",
                        extra={
                            "label_name": name,
                            "value_type": type(lv.get("value")).__name__,
                        },
                    )
                    continue

                # Extract statistic type from label name
                statistic_type = extract_statistic_type(name) or "unknown"

                # Try to get numeric value
                val = lv.get("value")
                numeric_val = None
                if isinstance(val, (int, float)):
                    numeric_val = float(val)
                else:
                    try:
                        numeric_val = float(str(val))
                    except (TypeError, ValueError):
                        # Track skipped labels with non-numeric values
                        skipped_info = {
                            "label": name,
                            "value": str(val)[:50],
                            "reason": "non_numeric",
                        }
                        if skipped_info not in skipped_labels:
                            skipped_labels.append(skipped_info)
                        logger.debug(
                            "boot_time.skipped_label_value",
                            extra={
                                "label_name": name,
                                "value": str(val)[:100],
                                "value_type": type(val).__name__,
                                "metric_id": metric_id,
                            },
                        )

                # Group boot phases by statistic type for summing
                if "phase" in metric_id:
                    if statistic_type not in phase_data_by_stat_type:
                        phase_data_by_stat_type[statistic_type] = {}
                        missing_phases_by_stat_type[statistic_type] = []

                    if numeric_val is not None:
                        phase_data_by_stat_type[statistic_type][metric_id] = numeric_val
                    else:
                        # Missing/non-numeric phase - will be treated as 0
                        phase_data_by_stat_type[statistic_type][metric_id] = 0.0
                        missing_phases_by_stat_type[statistic_type].append(metric_id)
                # Collect KPI timestamps separately
                elif "timestamp" in metric_id and numeric_val is not None:
                    kpi_data.append((metric_id, numeric_val, statistic_type))

            # PHASE 2: Create metric points for phases and calculate totals
            for stat_type, phases in phase_data_by_stat_type.items():
                # Build base dimensions (3D matrix: target × mode × os_id)
                # Plus metadata fields from labels
                dimensions = {}
                if stat_type != "unknown":
                    dimensions["statistic_type"] = stat_type
                # Always include 3D matrix dimensions, use "undefined" for missing
                dimensions["os_id"] = item_os_id or "undefined"
                dimensions["mode"] = item_mode or "undefined"
                dimensions["target"] = item_target or "undefined"

                # Add metadata fields from labels (now available on fast path!)
                # Always include for consistent grouping, use "undefined" for missing
                dimensions["release"] = item_release or "undefined"
                dimensions["image_name"] = item_image_name or "undefined"
                dimensions["samples"] = (
                    str(item_samples) if item_samples is not None else "undefined"
                )
                dimensions["user"] = item_user or "undefined"
                dimensions["build"] = item_build or "undefined"

                # Add missing phases info if any
                missing_list = missing_phases_by_stat_type.get(stat_type, [])
                if missing_list:
                    dimensions["missing_phases"] = ",".join(
                        [p.split(".")[-1].replace("_ms", "") for p in missing_list]
                    )

                dimensions_value = dimensions if dimensions else None

                # Emit each phase metric (skip invalid floats)
                for phase_metric_id, phase_value in phases.items():
                    if _is_valid_float(phase_value):
                        points.append(
                            MetricPoint(
                                metric_id=phase_metric_id,
                                timestamp=ts_dt or datetime.now(timezone.utc),
                                value=phase_value,
                                unit="ms",
                                dimensions=dimensions_value,
                                source=self.id,
                            )
                        )
                    else:
                        logger.warning(
                            "boot_time.invalid_float_skipped",
                            extra={
                                "metric_id": phase_metric_id,
                                "value": phase_value,
                                "details": "Float value is inf or nan, skipping",
                            },
                        )

                # Calculate and emit total boot time (sum of all phases)
                total_boot_time = sum(phases.values())
                if _is_valid_float(total_boot_time):
                    points.append(
                        MetricPoint(
                            metric_id="boot.time.total_ms",
                            timestamp=ts_dt or datetime.now(timezone.utc),
                            value=total_boot_time,
                            unit="ms",
                            dimensions=dimensions_value,
                            source=self.id,
                        )
                    )
                else:
                    logger.warning(
                        "boot_time.invalid_float_skipped",
                        extra={
                            "metric_id": "boot.time.total_ms",
                            "value": total_boot_time,
                            "details": "Float value is inf or nan, skipping",
                        },
                    )

            # PHASE 3: Add KPI timestamps (skip invalid floats)
            for kpi_metric_id, kpi_value, stat_type in kpi_data:
                if not _is_valid_float(kpi_value):
                    logger.warning(
                        "boot_time.invalid_float_skipped",
                        extra={
                            "metric_id": kpi_metric_id,
                            "value": kpi_value,
                            "details": "Float value is inf or nan, skipping",
                        },
                    )
                    continue

                # Build dimensions (3D matrix: target × mode × os_id)
                # Plus metadata fields from labels
                dimensions = {}
                if stat_type != "unknown":
                    dimensions["statistic_type"] = stat_type
                # Always include 3D matrix dimensions, use "undefined" for missing
                dimensions["os_id"] = item_os_id or "undefined"
                dimensions["mode"] = item_mode or "undefined"
                dimensions["target"] = item_target or "undefined"

                # Add metadata fields from labels (now available on fast path!)
                # Always include for consistent grouping, use "undefined" for missing
                dimensions["release"] = item_release or "undefined"
                dimensions["image_name"] = item_image_name or "undefined"
                dimensions["samples"] = (
                    str(item_samples) if item_samples is not None else "undefined"
                )
                dimensions["user"] = item_user or "undefined"
                dimensions["build"] = item_build or "undefined"

                dimensions_value = dimensions if dimensions else None

                points.append(
                    MetricPoint(
                        metric_id=kpi_metric_id,
                        timestamp=ts_dt or datetime.now(timezone.utc),
                        value=kpi_value,
                        unit="ms",
                        dimensions=dimensions_value,
                        source=self.id,
                    )
                )

        # Log extraction summary
        metric_id_counts: Dict[str, int] = {}
        for p in points:
            metric_id_counts[p.metric_id] = metric_id_counts.get(p.metric_id, 0) + 1

        has_boot_phases = any("phase" in mid for mid in metric_id_counts)
        has_total = any("total" in mid for mid in metric_id_counts)

        # Log detailed extraction summary
        logger.info(
            "boot_time.extract_from_label_values.complete",
            extra={
                "items_processed": items_processed,
                "filtered_by_run_type": filtered_by_run_type,
                "filtered_by_os": filtered_by_os,
                "labels_found": labels_found,
                "metrics_extracted": len(points),
                "metric_id_counts": metric_id_counts,
                "has_boot_phases": has_boot_phases,
                "has_total_boot_time": has_total,
                "skipped_labels_count": len(skipped_labels),
            },
        )

        # Log warning if we only have total boot time but no phases
        if has_total and not has_boot_phases and len(labels_found) > 0:
            logger.warning(
                "boot_time.missing_boot_phases",
                extra={
                    "details": (
                        "Only total boot time extracted, no boot phases found. "
                        "This may indicate: (1) Horreum schema not exporting "
                        "BOOT0-BOOT4 labels, (2) Boot phase values are non-numeric "
                        "(e.g., 'Need to collect'), or (3) Test data doesn't include "
                        "boot phase measurements."
                    ),
                    "labels_found": labels_found,
                    "skipped_labels": skipped_labels[:10],  # Show first 10
                },
            )

        return points

    @staticmethod
    def _compute_statistics(
        samples: List[float],
    ) -> Dict[str, float]:
        """Compute statistical metrics from a list of samples.

        Wrapper around the shared compute_statistics() utility that maintains
        backward compatibility by returning a dict instead of a Statistics object.

        See src.domain.utils.statistics.compute_statistics() for full documentation.

        Parameters
        ----------
        samples : List[float]
            Array of measurements (e.g., boot times in milliseconds)

        Returns
        -------
        Dict[str, float]
            Dictionary with keys: mean, median, p95, p99, std_dev, cv, min, max
            Returns empty dict if samples is empty or invalid.
        """
        stats = compute_statistics(samples)
        if stats is None:
            return {}

        # Convert Statistics object to dict for backward compatibility
        result = {
            "mean": stats.mean,
            "median": stats.median,
            "min": stats.min,
            "max": stats.max,
            "p95": stats.p95,
            "p99": stats.p99,
        }

        # Add optional fields only if present
        if stats.std_dev is not None:
            result["std_dev"] = stats.std_dev
        if stats.cv is not None:
            result["cv"] = stats.cv

        return result

    def _extract_rhivos_local(
        self, data: Dict[str, object], os_filter: Optional[str] = None
    ) -> List[MetricPoint]:
        """Extract from RHIVOS local collector format.

        Expected shape (example):
        {
          "boot_metrics": {
            "total_boot_time_ms": 12500,
            "phases": {
              "kernel": 3000,
              "initrd": 1500,
              "userspace": 5500
            }
          },
          "system_info": {"os_id": "rhel-9.2", "mode": "standard"},
          "timestamp": "2025-09-22T10:30:00Z"
        }

        Parameters
        ----------
        data : Dict[str, object]
            Dataset in RHIVOS local format
        os_filter : Optional[str]
            If provided, only extract if os_id matches (case-insensitive)
        """
        points: List[MetricPoint] = []
        boot = data.get("boot_metrics")
        if not isinstance(boot, dict):
            return points

        # Timestamp
        ts = _parse_timestamp(str(data.get("timestamp")))
        if ts is None:
            meta = data.get("metadata")
            if isinstance(meta, dict):
                ts = _parse_timestamp(str(meta.get("collection_timestamp")))
        if ts is None:
            ts = datetime.now(timezone.utc)

        # Dimensions (extract os_id, mode, target for 3D matrix)
        dims: Dict[str, str] = {}
        sysinfo = data.get("system_info")
        if isinstance(sysinfo, dict):
            os_id = sysinfo.get("os_id")
            mode = sysinfo.get("mode")
            target = sysinfo.get("target") or sysinfo.get("hardware")
            if isinstance(os_id, str):
                dims["os_id"] = os_id
                # Apply OS filtering if requested
                if os_filter and os_id.lower() != os_filter.lower():
                    return points  # Skip this dataset
            if isinstance(mode, str):
                dims["mode"] = mode
            if isinstance(target, str):
                dims["target"] = target

        # Extract total boot time
        total = boot.get("total_boot_time_ms")
        if isinstance(total, (int, float)):
            points.append(
                MetricPoint(
                    metric_id="boot.time.total_ms",
                    timestamp=ts,
                    value=float(total),
                    unit="ms",
                    dimensions=dims or None,
                    source=self.id,
                )
            )

        # Extract phase durations
        # Note: Not all datasets will have all 5 phases. Extract what's available.
        phases = boot.get("phases")
        if isinstance(phases, dict):
            # Kernel phase
            # Extract phase values safely - use .get() to avoid KeyError
            kernel_val = phases.get("kernel")
            if isinstance(kernel_val, (int, float)):
                points.append(
                    MetricPoint(
                        metric_id="boot.phase.kernel_ms",
                        timestamp=ts,
                        value=float(kernel_val),
                        unit="ms",
                        dimensions=dims or None,
                        source=self.id,
                    )
                )
            # Initrd phase
            initrd_val = phases.get("initrd")
            if isinstance(initrd_val, (int, float)):
                points.append(
                    MetricPoint(
                        metric_id="boot.phase.initrd_ms",
                        timestamp=ts,
                        value=float(initrd_val),
                        unit="ms",
                        dimensions=dims or None,
                        source=self.id,
                    )
                )
            # Switchroot phase
            switchroot_val = phases.get("switchroot")
            if isinstance(switchroot_val, (int, float)):
                points.append(
                    MetricPoint(
                        metric_id="boot.phase.switchroot_ms",
                        timestamp=ts,
                        value=float(switchroot_val),
                        unit="ms",
                        dimensions=dims or None,
                        source=self.id,
                    )
                )
            # Userspace/SystemInit phase
            userspace_val = phases.get("userspace")
            if isinstance(userspace_val, (int, float)):
                points.append(
                    MetricPoint(
                        metric_id="boot.phase.system_init_ms",
                        timestamp=ts,
                        value=float(userspace_val),
                        unit="ms",
                        dimensions=dims or None,
                        source=self.id,
                    )
                )

        return points

    def _extract_horreum_v4(
        self, data: Dict[str, object], os_filter: Optional[str] = None
    ) -> List[MetricPoint]:
        """Extract from Horreum v4 boot-time verbose schema.

        Expected hints:
        - "$schema": "urn:boot-time-verbose:04" or ":06"
        - For v04: "test_results" array with satime, clktick, earlyservice, dlkm
        - For v06: "boot_time" list with "boot_logs" entries; total inferred from
          max activated; timestamps from top-level start_time/end_time
        - Dimensions from system_config (v04) or rhivos_config (v06)

        Parameters
        ----------
        data : Dict[str, object]
            Dataset in Horreum v4/v6 format
        os_filter : Optional[str]
            If provided, only extract if os_id matches (case-insensitive)
        """
        points: List[MetricPoint] = []
        schema = data.get("$schema")
        if not isinstance(schema, str) or "boot-time-verbose" not in schema:
            # Still attempt to parse if fields match even without $schema
            pass

        # v04 path: test_results based
        results = data.get("test_results")
        if isinstance(results, list) and results:
            first = results[0] if isinstance(results[0], dict) else None
            if first:
                # Get timestamp
                ts = _parse_timestamp(str(first.get("end_time"))) or _parse_timestamp(
                    str(first.get("start_time"))
                )
                if ts is None:
                    ts = datetime.now(timezone.utc)

                # Get dimensions (extract os_id, mode, target for 3D matrix)
                dims: Dict[str, str] = {}
                syscfg = data.get("system_config")
                if isinstance(syscfg, dict):
                    os_id = syscfg.get("os_id")
                    mode = syscfg.get("mode")
                    image_target = syscfg.get("image_target")
                    if isinstance(os_id, str):
                        dims["os_id"] = os_id
                        # Apply OS filtering if requested
                        if os_filter and os_id.lower() != os_filter.lower():
                            return points  # Skip this dataset
                    if isinstance(mode, str):
                        dims["mode"] = mode
                    if isinstance(image_target, str):
                        # In v4 datasets, image_target may be hardware platform
                        # or systemd target - store as "target" dimension
                        dims["target"] = image_target

                # Extract total boot time
                satime = first.get("satime")
                if isinstance(satime, dict):
                    total = satime.get("total")
                    if isinstance(total, (int, float)):
                        points.append(
                            MetricPoint(
                                metric_id="boot.time.total_ms",
                                timestamp=ts,
                                value=float(total),
                                unit="ms",
                                dimensions=dims or None,
                                source=self.id,
                            )
                        )

                    # Extract phase durations from satime
                    kernel = satime.get("kernel")
                    if isinstance(kernel, (int, float)):
                        points.append(
                            MetricPoint(
                                metric_id="boot.phase.kernel_ms",
                                timestamp=ts,
                                value=float(kernel),
                                unit="ms",
                                dimensions=dims or None,
                                source=self.id,
                            )
                        )

                    initrd = satime.get("initrd")
                    if isinstance(initrd, (int, float)):
                        points.append(
                            MetricPoint(
                                metric_id="boot.phase.initrd_ms",
                                timestamp=ts,
                                value=float(initrd),
                                unit="ms",
                                dimensions=dims or None,
                                source=self.id,
                            )
                        )

                    userspace = satime.get("userspace")
                    if isinstance(userspace, (int, float)):
                        points.append(
                            MetricPoint(
                                metric_id="boot.phase.system_init_ms",
                                timestamp=ts,
                                value=float(userspace),
                                unit="ms",
                                dimensions=dims or None,
                                source=self.id,
                            )
                        )

                    # Switchroot phase (if present in satime)
                    switchroot = satime.get("switchroot")
                    if isinstance(switchroot, (int, float)):
                        points.append(
                            MetricPoint(
                                metric_id="boot.phase.switchroot_ms",
                                timestamp=ts,
                                value=float(switchroot),
                                unit="ms",
                                dimensions=dims or None,
                                source=self.id,
                            )
                        )

                # Extract kernel_pre_timer from clktick
                clktick = first.get("clktick")
                if isinstance(clktick, dict):
                    time_init_ts = clktick.get("time_init_ts")
                    if isinstance(time_init_ts, (int, float)):
                        points.append(
                            MetricPoint(
                                metric_id="boot.phase.kernel_pre_timer_ms",
                                timestamp=ts,
                                value=float(time_init_ts),
                                unit="ms",
                                dimensions=dims or None,
                                source=self.id,
                            )
                        )

                # Extract critical timestamps
                # Early Service
                earlyservice = first.get("earlyservice")
                if isinstance(earlyservice, dict):
                    earlyservice_ts = earlyservice.get("earlyservice_ts")
                    if isinstance(earlyservice_ts, (int, float)):
                        points.append(
                            MetricPoint(
                                metric_id="boot.timestamp.early_service_ms",
                                timestamp=ts,
                                value=float(earlyservice_ts),
                                unit="ms",
                                dimensions=dims or None,
                                source=self.id,
                            )
                        )

                # Start Kmod Load
                dlkm = first.get("dlkm")
                if isinstance(dlkm, dict):
                    start_kmod_load_ts = dlkm.get("start_kmod_load_ts")
                    if isinstance(start_kmod_load_ts, (int, float)):
                        points.append(
                            MetricPoint(
                                metric_id="boot.timestamp.start_kmod_load_ms",
                                timestamp=ts,
                                value=float(start_kmod_load_ts),
                                unit="ms",
                                dimensions=dims or None,
                                source=self.id,
                            )
                        )

                # Extract first_service and network_online from timing_details
                timing_details = first.get("timing_details")
                if isinstance(timing_details, list):
                    first_service_ts = None
                    network_online_ts = None

                    for service in timing_details:
                        if not isinstance(service, dict):
                            continue

                        service_name = service.get("name", "")
                        activated = service.get("activated")

                        if not isinstance(activated, (int, float)):
                            continue

                        # First service: earliest activated timestamp
                        if first_service_ts is None or activated < first_service_ts:
                            first_service_ts = activated

                        # Network online: look for network-related services
                        if isinstance(service_name, str) and any(
                            net in service_name.lower()
                            for net in [
                                "network",
                                "networkmanager",
                                "systemd-networkd",
                            ]
                        ):
                            if (
                                network_online_ts is None
                                or activated < network_online_ts
                            ):
                                network_online_ts = activated

                    if first_service_ts is not None:
                        points.append(
                            MetricPoint(
                                metric_id="boot.timestamp.first_service_ms",
                                timestamp=ts,
                                value=float(first_service_ts),
                                unit="ms",
                                dimensions=dims or None,
                                source=self.id,
                            )
                        )

                    if network_online_ts is not None:
                        points.append(
                            MetricPoint(
                                metric_id="boot.timestamp.network_online_ms",
                                timestamp=ts,
                                value=float(network_online_ts),
                                unit="ms",
                                dimensions=dims or None,
                                source=self.id,
                            )
                        )

                # Fallback: try reboot.total_et for total if satime not present
                if not points:
                    reboot_data = first.get("reboot")
                    if isinstance(reboot_data, dict):
                        reboot = reboot_data
                    total_et = reboot.get("total_et")
                    if isinstance(total_et, (int, float)):
                        points.append(
                            MetricPoint(
                                metric_id="boot.time.total_ms",
                                timestamp=ts,
                                value=float(total_et),
                                unit="ms",
                                dimensions=dims or None,
                                source=self.id,
                            )
                        )

                if points:
                    return points

        # v06 path: boot_time/boot_logs based (fallback for structured format)
        boot_time = data.get("boot_time")
        if isinstance(boot_time, list) and boot_time:
            # Single-sample structured format: boot_time is an array of dicts
            first_bt = boot_time[0] if isinstance(boot_time[0], dict) else None
            logs = first_bt.get("boot_logs") if isinstance(first_bt, dict) else None
            # derive total from timestamps if available (v05/06)
            ts_end = _parse_timestamp(str(data.get("end_time")))
            ts_start = _parse_timestamp(str(data.get("start_time")))
            ts = ts_end or ts_start or datetime.now(timezone.utc)

            total_ms_from_ts: Optional[float] = None
            if ts_end and ts_start:
                delta = ts_end - ts_start
                total_ms_from_ts = delta.total_seconds() * 1000.0

            max_value = None
            max_keys = ("activated", "time", "duration", "elapsed")
            if isinstance(logs, list) and logs:
                for entry in logs:
                    if isinstance(entry, dict):
                        for k in max_keys:
                            v = entry.get(k)
                            if isinstance(v, (int, float)):
                                max_value = (
                                    v if max_value is None else max(max_value, v)
                                )

            total_ms: Optional[float] = None
            # prefer timestamp-derived when consistent
            if isinstance(total_ms_from_ts, (int, float)) and total_ms_from_ts > 0:
                total_ms = float(total_ms_from_ts)
            elif isinstance(max_value, (int, float)):
                # Values may be in microseconds or nanoseconds; scale if large
                total_ms = (
                    max_value / 1_000_000.0
                    if max_value > 1_000_000
                    else float(max_value)
                )

            dims_v06: Dict[str, str] = {}
            rhcfg = data.get("rhivos_config")
            if isinstance(rhcfg, dict):
                os_id = rhcfg.get("os_id")
                mode = rhcfg.get("mode")
                target = rhcfg.get("image_target")
                if isinstance(os_id, str):
                    dims_v06["os_id"] = os_id
                    # Apply OS filtering if requested
                    if os_filter and os_id.lower() != os_filter.lower():
                        return points  # Skip this dataset
                if isinstance(mode, str):
                    dims_v06["mode"] = mode
                if isinstance(target, str):
                    dims_v06["target"] = target

            if total_ms is not None:
                points.append(
                    MetricPoint(
                        metric_id="boot.time.total_ms",
                        timestamp=ts,
                        value=float(total_ms),
                        unit="ms",
                        dimensions=dims_v06 or None,
                        source=self.id,
                    )
                )
                return points

        return points


# Import register here to avoid circular imports
from ..plugins import register  # noqa: E402

register(BootTimePlugin())
