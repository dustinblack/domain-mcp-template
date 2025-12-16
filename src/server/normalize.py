"""Shared parameter normalization utilities for server tool handlers.

This module centralizes input normalization so both stdio and HTTP servers
apply identical semantics when accepting user/client parameters.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict


def normalize_get_key_metrics_params(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize user/client-provided params for get_key_metrics.

    - Unwrap common nesting (e.g., {"params": {...}} or {"args": {...}})
    - Coerce types (e.g., int test_id -> str)
    - Map synonyms (dataset_type -> dataset_types, source -> source_id, ...)
    - Handle relative dates ("30d", "30 days ago", "now")
    - Normalize dataset type aliases (e.g., "boot-time" -> "boot-time-verbose")
    - Provide defaults: source_id (horreum-stdio) and limit (10) when omitted
    - Remove unsupported cosmetic fields some clients add
    """

    params = raw.get("params", raw)

    # Unwrap args if the client double-nested inputs
    if isinstance(params.get("args"), dict) and not any(
        k in params for k in ("dataset_types", "data", "source_id")
    ):
        params = params["args"]

    # Synonyms → canonical
    if "dataset_type" in params and "dataset_types" not in params:
        params["dataset_types"] = [params.pop("dataset_type")]
    if "source" in params and "source_id" not in params:
        params["source_id"] = params.pop("source")
    for alt in ("testId", "test"):
        if alt in params and "test_id" not in params:
            params["test_id"] = params.pop(alt)
    for alt in ("runId", "run"):
        if alt in params and "run_id" not in params:
            params["run_id"] = params.pop(alt)
    if "schema" in params and "schema_uri" not in params:
        params["schema_uri"] = params.pop("schema")

    # Time window synonyms (from_time, from_timestamp, fromTimestamp → from)
    for from_synonym in ("from_time", "from_timestamp", "fromTimestamp"):
        if from_synonym in params and "from" not in params:
            params["from"] = params.pop(from_synonym)
            break
    for to_synonym in ("to_time", "to_timestamp", "toTimestamp"):
        if to_synonym in params and "to" not in params:
            params["to"] = params.pop(to_synonym)
            break

    # Coerce types
    if isinstance(params.get("test_id"), int):
        params["test_id"] = str(params["test_id"])  # e.g., 294 -> "294"
    if isinstance(params.get("run_id"), int):
        params["run_id"] = str(params["run_id"])  # e.g., 127723 -> "127723"
    if "limit" in params:
        try:
            params["limit"] = int(params["limit"])  # tolerate strings
        except (ValueError, TypeError):
            pass

    def _parse_relative_date(value: str) -> str:
        if not isinstance(value, str):
            return value
        # Handle "now"
        if value.lower() == "now":
            return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        # Handle "X days ago"
        days_ago_match = re.match(r"^(\d+)\s+days?\s+ago$", value, re.IGNORECASE)
        if days_ago_match:
            days = int(days_ago_match.group(1))
            past_date = datetime.now() - timedelta(days=days)
            return past_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        # Handle "Xd"
        match = re.match(r"^(\d+)d$", value)
        if match:
            days = int(match.group(1))
            past_date = datetime.now() - timedelta(days=days)
            return past_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        return value

    if "from" in params:
        params["from"] = _parse_relative_date(params["from"])
    if "to" in params:
        params["to"] = _parse_relative_date(params["to"])

    # Normalize dataset type aliases
    alias_map = {
        "boot-time": "boot-time-verbose",
        "boot_time": "boot-time-verbose",
        "boot": "boot-time-verbose",
    }
    dtypes = params.get("dataset_types")
    if isinstance(dtypes, list):
        params["dataset_types"] = [alias_map.get(x, x) for x in dtypes]
    elif isinstance(dtypes, str):
        params["dataset_types"] = [alias_map.get(dtypes, dtypes)]

    # Domain knowledge: Detect when test_id is actually an OS identifier/label
    # Common pattern: "boot time runs for rhel" → test_id="rhel" (WRONG)
    # Should be: test_id="boot-time-verbose", filter/group by OS label
    # Primary OS identifiers: "rhel" and "autosd"
    known_os_identifiers = {
        "rhel",
        "rhel-9",
        "rhel-8",
        "rhel9",
        "rhel8",
        # "rhivos",  # Alias for rhel
        "autosd",
        "autosd-9",
        "fedora",
        "centos",
        "centos-stream",
        "fedora-coreos",
        "fcos",
    }

    # Map OS aliases to canonical identifiers
    os_alias_map = {
        "rhel": "rhel",
        "autosd": "autosd",
        # "rhivos": "rhel",  # Example: Domain specific alias mapping
    }

    # Handle explicit os_id parameter
    os_id_val = params.get("os_id", "").lower()
    if os_id_val:
        # Normalize OS alias (e.g., "rhivos" → "rhel")
        canonical_os = os_alias_map.get(os_id_val, os_id_val)
        params["_detected_os_filter"] = canonical_os
        # Auto-configure dataset_types for boot time if not specified
        if not params.get("dataset_types"):
            params["dataset_types"] = ["boot-time-verbose"]

    # Also check if test_id contains an OS identifier (legacy detection)
    test_id_val = params.get("test_id", "").lower()
    if test_id_val in known_os_identifiers:
        # AI likely misinterpreted OS name as test ID
        # For boot time queries, the test is "boot-time-verbose"
        # The OS should be used for filtering, not as test_id
        if not params.get("dataset_types"):
            # Infer this is a boot time query
            params["dataset_types"] = ["boot-time-verbose"]
        # Clear the incorrect test_id - let auto-discovery find boot-time-verbose
        params.pop("test_id")
        # Normalize OS alias (e.g., "rhivos" → "rhel")
        canonical_os = os_alias_map.get(test_id_val, test_id_val)
        params["_detected_os_filter"] = canonical_os  # Internal hint for logging

    # Domain knowledge: Detect run type identifiers (nightly, CI, release, manual)
    # When users ask for "nightly" data, we need to filter by Run type label
    # Modern data: Filter by 'Run type' label (deterministic)
    # Legacy data: Search 'Test Description' label for keyword
    known_run_types = {"nightly", "ci", "release", "manual", "ad-hoc", "adhoc"}

    # Handle explicit run_type parameter (takes priority over auto-detection)
    if "run_type" in params or "runType" in params:
        run_type_val = params.get("run_type") or params.get("runType")
        if run_type_val:
            run_type_lower = str(run_type_val).lower()
            # Normalize ad-hoc variants
            if run_type_lower in {"ad-hoc", "adhoc"}:
                run_type_lower = "manual"
            params["_detected_run_type"] = run_type_lower
            # Clean up the explicit parameter (not needed downstream)
            params.pop("run_type", None)
            params.pop("runType", None)

    # Check if test_id contains a run type identifier
    # (only if run_type wasn't explicitly provided)
    if "_detected_run_type" not in params and test_id_val in known_run_types:
        # AI likely misinterpreted run type as test ID
        # Store this as a hint for label filtering
        params["_detected_run_type"] = test_id_val
        # Clear the incorrect test_id
        params.pop("test_id")
        # Auto-configure for boot time if not specified
        if not params.get("dataset_types"):
            params["dataset_types"] = ["boot-time-verbose"]

    # Also check for run type keywords in other string parameters
    # This helps detect patterns like: "show me nightly boot times"
    # (only if run_type wasn't explicitly provided)
    if "_detected_run_type" not in params:
        for key in ["test_id", "schema_uri"]:
            val = str(params.get(key, "")).lower()
            for run_type in known_run_types:
                if run_type in val:
                    params["_detected_run_type"] = run_type
                    # If it was misplaced in test_id, remove it
                    if key == "test_id":
                        params.pop("test_id", None)
                        if not params.get("dataset_types"):
                            params["dataset_types"] = ["boot-time-verbose"]
                    break

    # Note: source_id auto-selection is handled by the tool handlers
    # (stdio, HTTP, MCP-over-HTTP), not in normalization.
    # Each handler calls get_available_source_ids() and selects the first.

    # Provide a reasonable default page size if not specified
    # The server automatically paginates to fetch ALL results.
    # This limit controls page size, not total results.
    # Default of 100 provides good performance for most queries.
    if "limit" not in params:
        params["limit"] = 100

    # Remove unsupported fields that clients might add
    for unsupported in ("output_format", "table_format"):
        params.pop(unsupported, None)

    return params
