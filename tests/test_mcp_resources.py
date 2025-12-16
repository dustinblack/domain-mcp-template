"""
Tests for MCP Resources implementation.

Validates that domain knowledge resources are accessible via both
stdio (FastMCP) and HTTP (FastAPI) interfaces.
"""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from src.server.http import create_app
from src.server.resources import get_registry, read_resource


def test_resource_registry_loads_all_resources():
    """Test that ResourceRegistry loads all JSON resources."""
    registry = get_registry()
    resources = registry.list_resources()

    # Should have at least 7 resources (4 glossary + 3 examples)
    assert len(resources) >= 7

    # Check glossary resources
    glossary_uris = [
        r["uri"] for r in resources if r["uri"].startswith("domain://glossary/")
    ]
    assert "domain://glossary/boot-time" in glossary_uris
    assert "domain://glossary/os-identifiers" in glossary_uris
    assert "domain://glossary/platform-identifiers" in glossary_uris
    assert "domain://glossary/metadata-fields" in glossary_uris

    # Check example resources
    example_uris = [
        r["uri"] for r in resources if r["uri"].startswith("domain://examples/")
    ]
    assert "domain://examples/boot-time-basic" in example_uris
    assert "domain://examples/filter-by-os" in example_uris
    assert "domain://examples/statistical-analysis" in example_uris


def test_resource_metadata_structure():
    """Test that resource metadata has required fields."""
    registry = get_registry()
    resources = registry.list_resources()

    for resource in resources:
        assert "uri" in resource
        assert "name" in resource
        assert "description" in resource
        assert "mimeType" in resource
        assert resource["mimeType"] == "application/json"


def test_read_boot_time_glossary():
    """Test reading boot-time glossary resource."""
    result = read_resource("domain://glossary/boot-time")

    assert result is not None
    assert "contents" in result
    assert len(result["contents"]) == 1

    content = result["contents"][0]
    assert content["uri"] == "domain://glossary/boot-time"
    assert content["mimeType"] == "application/json"
    assert "text" in content

    # Parse JSON content
    data = json.loads(content["text"])
    assert data["domain"] == "boot-time"
    assert "boot_phases" in data
    assert "kpi_timestamps" in data
    assert "total_boot_time" in data


def test_read_os_identifiers_glossary():
    """Test reading os-identifiers glossary resource."""
    result = read_resource("domain://glossary/os-identifiers")

    assert result is not None
    content = json.loads(result["contents"][0]["text"])

    assert content["domain"] == "os-identifiers"
    assert "primary_os" in content
    assert "rhel" in content["primary_os"]
    assert "autosd" in content["primary_os"]
    assert content["primary_os"]["rhel"]["aliases"] == []


def test_read_platform_identifiers_glossary():
    """Test reading platform-identifiers glossary resource."""
    result = read_resource("domain://glossary/platform-identifiers")

    assert result is not None
    content = json.loads(result["contents"][0]["text"])

    assert content["domain"] == "platform-identifiers"
    assert "platforms" in content
    assert "qemu" in content["platforms"]
    assert "intel-nuc" in content["platforms"]
    assert "raspberry-pi" in content["platforms"]
    assert "orin" in content["platforms"]


def test_read_metadata_fields_glossary():
    """Test reading metadata-fields glossary resource."""
    result = read_resource("domain://glossary/metadata-fields")

    assert result is not None
    content = json.loads(result["contents"][0]["text"])

    assert content["domain"] == "metadata-fields"
    assert "report_metadata" in content
    assert "three_d_matrix" in content

    # Check that all 9 metadata fields are present
    metadata_names = [field["name"] for field in content["report_metadata"]]
    assert "RHIVOS Release" in metadata_names
    assert "RHIVOS OS ID" in metadata_names
    assert "RHIVOS Target" in metadata_names


def test_read_boot_time_basic_example():
    """Test reading boot-time-basic example resource."""
    result = read_resource("domain://examples/boot-time-basic")

    assert result is not None
    content = json.loads(result["contents"][0]["text"])

    assert content["name"] == "Basic Boot Time Query"
    assert "query_examples" in content
    assert "tool_call" in content
    assert content["tool_call"]["tool"] == "get_key_metrics"


def test_read_filter_by_os_example():
    """Test reading filter-by-os example resource."""
    result = read_resource("domain://examples/filter-by-os")

    assert result is not None
    content = json.loads(result["contents"][0]["text"])

    assert content["name"] == "Filter Boot Time by OS"
    assert "tool_call" in content
    assert "os_id" in content["tool_call"]["params"]


def test_read_statistical_analysis_example():
    """Test reading statistical-analysis example resource."""
    result = read_resource("domain://examples/statistical-analysis")

    assert result is not None
    content = json.loads(result["contents"][0]["text"])

    assert content["name"] == "Statistical Analysis"
    assert "statistical_metrics" in content
    assert "always_returned" in content["statistical_metrics"]

    # Check all 7 default metrics
    metrics = [
        metric["name"] for metric in content["statistical_metrics"]["always_returned"]
    ]
    assert "min" in metrics
    assert "mean" in metrics
    assert "max" in metrics
    assert "p95" in metrics
    assert "p99" in metrics
    assert "std_dev" in metrics
    assert "cv" in metrics


def test_read_nonexistent_resource():
    """Test reading a resource that doesn't exist."""
    result = read_resource("domain://glossary/nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_http_list_resources_endpoint():
    """Test HTTP endpoint for listing resources."""
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/resources")
        assert response.status_code == 200

        data = response.json()
        assert "resources" in data
        assert len(data["resources"]) >= 7

        # Check for specific resources
        uris = [r["uri"] for r in data["resources"]]
        assert "domain://glossary/boot-time" in uris
        assert "domain://examples/boot-time-basic" in uris


@pytest.mark.asyncio
async def test_http_read_resource_endpoint():
    """Test HTTP endpoint for reading a specific resource."""
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Read boot-time glossary
        response = await client.get("/resources/glossary/boot-time")
        assert response.status_code == 200

        data = response.json()
        assert "contents" in data
        assert len(data["contents"]) == 1

        content = data["contents"][0]
        assert content["uri"] == "domain://glossary/boot-time"
        assert content["mimeType"] == "application/json"

        # Parse JSON text
        resource_data = json.loads(content["text"])
        assert resource_data["domain"] == "boot-time"


@pytest.mark.asyncio
async def test_http_read_nonexistent_resource():
    """Test HTTP endpoint returns 404 for nonexistent resource."""
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/resources/glossary/nonexistent")
        assert response.status_code == 404
