"""
TEMPLATE: Unit test for your domain plugin

This test demonstrates how to:
1. Load fixtures (source response and expected metrics)
2. Run your plugin's extract() method
3. Validate the output matches expectations

TODO: Rename this file to match your domain (e.g., test_payment_latency_plugin.py)
TODO: Replace MyDomainPlugin with your actual plugin class
TODO: Update fixture paths to match your domain
TODO: Uncomment and run when ready
"""

import json
import pytest
from pathlib import Path

# TODO: Uncomment when you've created your plugin
# from src.domain.plugins.my_domain import MyDomainPlugin


# TODO: Uncomment this test when ready
# @pytest.mark.asyncio
# async def test_plugin_extraction():
#     """
#     Test that plugin correctly extracts metrics from source data.
#     """
#     # Load source response fixture
#     fixture_path = Path(__file__).parent / "fixtures" / "template" / "source_response_sample.json"
#     with open(fixture_path) as f:
#         source_data = json.load(f)
#     
#     # Load expected metrics
#     expected_path = Path(__file__).parent / "fixtures" / "template" / "expected_metrics.json"
#     with open(expected_path) as f:
#         expected = json.load(f)
#     
#     # Create plugin instance
#     plugin = MyDomainPlugin()
#     
#     # Extract metrics
#     datasets = source_data["datasets"]
#     results = []
#     for dataset in datasets:
#         points = await plugin.extract(
#             json_body=dataset["data"],
#             refs={"test_id": dataset["test_id"], "id": dataset["id"]}
#         )
#         results.extend(points)
#     
#     # Validate results
#     assert len(results) == len(expected["metrics"])
#     
#     for actual, expected_metric in zip(results, expected["metrics"]):
#         assert actual.timestamp.isoformat() == expected_metric["timestamp"].replace("Z", "+00:00")
#         assert actual.metric_name == expected_metric["metric_name"]
#         assert actual.value == expected_metric["value"]
#         assert actual.unit == expected_metric["unit"]
#         assert actual.dimensions == expected_metric["dimensions"]


# TODO: Add more tests
# @pytest.mark.asyncio
# async def test_plugin_with_filters():
#     """Test that plugin correctly applies dimension filters."""
#     pass
# 
# @pytest.mark.asyncio
# async def test_plugin_handles_missing_data():
#     """Test that plugin gracefully handles missing fields."""
#     pass
# 
# @pytest.mark.asyncio
# async def test_plugin_unit_conversion():
#     """Test that plugin correctly converts units."""
#     pass


# Placeholder test so pytest doesn't complain about empty file
def test_template_placeholder():
    """
    TODO: Remove this placeholder once you've implemented actual tests above.
    """
    assert True, "Replace this with real plugin tests"

