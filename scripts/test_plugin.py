#!/usr/bin/env python3
"""
Plugin Extraction Validator

Quick tool to test your plugin's extraction logic without running full tests.
Useful for iterative development and debugging.

Usage:
    python scripts/test_plugin.py --plugin my_plugin --sample tests/fixtures/my_domain/source_response_sample.json
    
    # With expected metrics comparison:
    python scripts/test_plugin.py --plugin my_plugin \
        --sample tests/fixtures/my_domain/source_response_sample.json \
        --expected tests/fixtures/my_domain/expected_metrics.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
import asyncio

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.domain.models import MetricPoint
from src.domain.plugins import get_plugin


def load_json_file(filepath: str) -> Any:
    """Load and parse JSON file."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: File not found: {filepath}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in {filepath}: {e}")
        sys.exit(1)


def format_metric_point(mp: MetricPoint) -> Dict[str, Any]:
    """Format MetricPoint for display."""
    return {
        "timestamp": mp.timestamp.isoformat() if mp.timestamp else None,
        "metric_name": mp.metric_id,  # Note: MetricPoint uses metric_id, not metric_name
        "value": mp.value,
        "unit": mp.unit,
        "dimensions": mp.dimensions or {}
    }


def compare_metrics(actual: List[MetricPoint], expected: List[Dict[str, Any]]) -> bool:
    """Compare actual extracted metrics with expected."""
    if len(actual) != len(expected):
        print(f"⚠️  Count mismatch: Expected {len(expected)} metrics, got {len(actual)}")
        return False
    
    all_match = True
    for i, (act, exp) in enumerate(zip(actual, expected)):
        print(f"\n--- Metric {i+1} ---")
        act_fmt = format_metric_point(act)
        
        # Compare each field
        for field in ["timestamp", "metric_name", "value", "unit", "dimensions"]:
            exp_val = exp.get(field)
            act_val = act_fmt.get(field)
            
            if exp_val != act_val:
                print(f"  ❌ {field}: Expected {exp_val!r}, got {act_val!r}")
                all_match = False
            else:
                print(f"  ✅ {field}: {act_val!r}")
    
    return all_match


async def main():
    parser = argparse.ArgumentParser(
        description="Test plugin extraction logic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--plugin",
        required=True,
        help="Plugin ID (e.g., 'my-plugin', 'elasticsearch-logs')"
    )
    parser.add_argument(
        "--sample",
        required=True,
        help="Path to sample source data JSON file"
    )
    parser.add_argument(
        "--expected",
        help="Path to expected metrics JSON file (optional, for comparison)"
    )
    parser.add_argument(
        "--refs",
        default="{}",
        help="JSON string of refs dict (optional, e.g., '{\"test_id\": \"123\"}')"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show full extracted metrics JSON"
    )
    
    args = parser.parse_args()
    
    # Load plugin
    print(f"🔌 Loading plugin: {args.plugin}")
    try:
        plugin = get_plugin(args.plugin)
    except Exception as e:
        print(f"❌ Error loading plugin '{args.plugin}': {e}")
        print("\nAvailable plugins:")
        from src.domain.plugins import list_plugins
        for p in list_plugins():
            print(f"  - {p}")
        sys.exit(1)
    
    # Load sample data
    print(f"📄 Loading sample data: {args.sample}")
    sample_data = load_json_file(args.sample)
    
    # Parse refs
    try:
        refs = json.loads(args.refs)
    except json.JSONDecodeError:
        print(f"❌ Error: Invalid JSON in --refs: {args.refs}")
        sys.exit(1)
    
    # Extract metrics
    print(f"\n⚙️  Running extraction...")
    try:
        # Handle different sample data structures
        if isinstance(sample_data, dict):
            if "hits" in sample_data:  # Elasticsearch response
                documents = [hit["_source"] for hit in sample_data["hits"]["hits"]]
            elif "datasets" in sample_data:  # Source MCP response
                documents = [ds.get("data", ds) for ds in sample_data["datasets"]]
            else:
                documents = [sample_data]  # Single document
        elif isinstance(sample_data, list):
            documents = sample_data
        else:
            print(f"❌ Error: Unexpected sample data structure")
            sys.exit(1)
        
        all_metrics = []
        for doc in documents:
            metrics = await plugin.extract(doc, refs)
            all_metrics.extend(metrics)
        
        print(f"✅ Extracted {len(all_metrics)} metrics\n")
        
    except Exception as e:
        print(f"❌ Error during extraction: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Display results
    if not all_metrics:
        print("⚠️  No metrics extracted!")
        print("\nPossible reasons:")
        print("  - Plugin filtering logic excluded all documents")
        print("  - Missing required fields in sample data")
        print("  - Check plugin's extract() method logic")
        sys.exit(1)
    
    print("📊 Extracted Metrics:")
    print("=" * 80)
    for i, mp in enumerate(all_metrics, 1):
        formatted = format_metric_point(mp)
        print(f"\n{i}. {formatted['metric_name']}")
        print(f"   Timestamp: {formatted['timestamp']}")
        print(f"   Value: {formatted['value']} {formatted['unit']}")
        if formatted['dimensions']:
            print(f"   Dimensions: {formatted['dimensions']}")
    
    if args.verbose:
        print("\n" + "=" * 80)
        print("Full JSON:")
        print(json.dumps([format_metric_point(mp) for mp in all_metrics], indent=2))
    
    # Compare with expected if provided
    if args.expected:
        print("\n" + "=" * 80)
        print("🔍 Comparing with expected metrics...")
        expected = load_json_file(args.expected)
        
        # Handle different expected formats
        if isinstance(expected, dict) and "expected_metrics" in expected:
            expected = expected["expected_metrics"]
        
        if compare_metrics(all_metrics, expected):
            print("\n✅ All metrics match expected output!")
            sys.exit(0)
        else:
            print("\n❌ Some metrics don't match expected output")
            sys.exit(1)
    else:
        print("\n💡 Tip: Use --expected to compare with expected output")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())

