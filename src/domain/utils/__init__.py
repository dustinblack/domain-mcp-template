"""
Shared utilities for domain plugins.

This module provides reusable utilities for validation, timestamps, statistics,
units, and aggregation. These utilities were extracted from the boot_time plugin
to enable code reuse across multiple domain plugins.

Modules
-------
validation
    Float validation and sanitization utilities
timestamps
    Timestamp parsing and conversion utilities
statistics
    Statistical analysis utilities (mean, median, p95, p99, std_dev, cv,
    confidence intervals, trend detection, anomaly detection)
units
    Unit conversion utilities for time (ms, s, min, h, d) and data (B, KB,
    MB, GB, TB) with auto-scaling for human-readable display
aggregation
    Data aggregation utilities with multiple strategies (mean, median, min,
    max, p95, p99, first, last, sum) and missing data handling (skip, zero,
    interpolate, forward_fill, raise)
"""

__all__ = []
