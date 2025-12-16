# Domain MCP Server Testing Guide

This guide provides comprehensive test cases to validate your Domain MCP server deployment, especially in containerized environments.

> **💡 Example Reference:** For concrete test examples using the PerfScale domain (boot time metrics), see [Example Domain: PerfScale](EXAMPLE_DOMAIN.md).

## Table of Contents

- [Quick Validation](#quick-validation)
- [Container Setup](#container-setup)
- [Test Categories](#test-categories)
  - [Raw Mode Tests](#raw-mode-tests)
  - [Source-Driven Mode Tests](#source-driven-mode-tests)
  - [Error Handling Tests](#error-handling-tests)
  - [Authentication Tests](#authentication-tests)
  - [Logging Validation](#logging-validation)
- [Integration Testing](#integration-testing)
- [Troubleshooting](#troubleshooting)

## About Test Examples

The test examples in this guide use the **PerfScale domain** (boot time metrics, Horreum source) as a reference implementation. When testing your own domain:
- Replace `boot-time-verbose` with your domain plugin identifiers
- Replace metric names (`boot_time_ms`, etc.) with your domain metrics
- Replace Horreum-specific endpoints with your Source MCP endpoints
- Use your domain's data schema and fixtures

See [Example Domain: PerfScale](EXAMPLE_DOMAIN.md) for details on the reference implementation.

## Quick Validation

Before running comprehensive tests, verify your server is running correctly:

```bash
# Health check (no auth required)
curl -s http://localhost:8080/health
# Expected: {"status":"ok"}

# Ready check (with auth)
curl -s -H 'Authorization: Bearer your-token' http://localhost:8080/ready
# Expected: {"status":"ready"}
```

## Container Setup

### Option 1: Domain MCP Only (Raw Mode Testing)

```bash
# Start your Domain MCP server
podman run -d --name domain-mcp-test \
  -p 127.0.0.1:8080:8080 \
  -e DOMAIN_MCP_HTTP_TOKEN=example-domain-token-12345 \
  -e DOMAIN_MCP_LOG_LEVEL=INFO \
  your-registry/your-domain-mcp:latest

# Verify startup logs show plugin registration
podman logs domain-mcp-test | grep -E "(Plugins loaded|Registered plugin)"
# Expected: Plugin registration messages with your domain plugin names
```

### Option 2: Full Integration (Domain MCP + Source MCP)

**Example using Horreum Source MCP (adapt for your source):**

```bash
# 1. Start Source MCP server (Horreum example)
podman run -d --name source-mcp-test \
  -p 127.0.0.1:3001:3000 \
  -e SOURCE_BASE_URL=https://your-source.example.com \
  -e HTTP_MODE_ENABLED=true \
  -e HTTP_AUTH_TOKEN=source-token \
  -e LOG_LEVEL=info \
  your-registry/your-source-mcp:latest

# 2. Create configuration file
cat > test-config.json << EOF
{
  "sources": {
    "your-source": {
      "endpoint": "http://127.0.0.1:3001",
      "api_key": "source-token",
      "type": "your_source_type",
      "timeout_seconds": 30
    }
  },
  "enabled_plugins": {
    "your-plugin-name": true
  }
}
EOF

# 3. Start your Domain MCP with configuration
podman run -d --name domain-mcp-test \
  --network host \
  -v $(pwd)/test-config.json:/config/config.json:ro,Z \
  -e DOMAIN_MCP_HTTP_TOKEN=domain-token \
  -e DOMAIN_MCP_CONFIG=/config/config.json \
  -e DOMAIN_MCP_LOG_LEVEL=INFO \
  your-registry/your-domain-mcp:latest

# 4. Verify both containers are running
curl -s http://localhost:3001/health && echo " ✅ Source MCP"
curl -s http://localhost:8080/health && echo " ✅ Domain MCP"
```

## Test Categories

### Raw Mode Tests

These tests validate the core plugin functionality without external dependencies.

#### Test 1: Basic Metric Extraction (PerfScale Example: Boot-Time Analysis)

```bash
curl -s -X POST \
  -H 'Authorization: Bearer example-domain-token-12345' \
  -H 'Content-Type: application/json' \
  http://localhost:8080/tools/get_key_metrics_raw \
  -d '{
    "dataset_types": ["boot-time-verbose"],
    "data": [{
      "$schema": "urn:boot-time-verbose:04",
      "test_results": [
        {
          "boot_time_ms": 12500,
          "kernel_time_ms": 3500,
          "userspace_time_ms": 9000,
          "timestamp": "2025-09-29T16:00:00Z"
        }
      ]
    }]
  }' | jq .
```

**Expected Result:**
```json
{
  "metric_points": [],
  "domain_model_version": "1.0.0"
}
```

#### Test 2: Empty Data Validation

```bash
curl -s -X POST \
  -H 'Authorization: Bearer example-domain-token-12345' \
  -H 'Content-Type: application/json' \
  http://localhost:8080/tools/get_key_metrics_raw \
  -d '{
    "dataset_types": ["boot-time-verbose"],
    "data": []
  }' | jq .
```

**Expected Result:**
```json
{
  "detail": {
    "detail": "1 validation error for GetKeyMetricsRequest...",
    "error_type": "validation_error",
    "available_options": null
  }
}
```

#### Test 3: Invalid Dataset Type

```bash
curl -s -X POST \
  -H 'Authorization: Bearer example-domain-token-12345' \
  -H 'Content-Type: application/json' \
  http://localhost:8080/tools/get_key_metrics_raw \
  -d '{
    "dataset_types": ["nonexistent-plugin"],
    "data": [{"test": "data"}]
  }' | jq .
```

**Expected Result:**
```json
{
  "detail": {
    "detail": "'nonexistent-plugin'",
    "error_type": "unknown_dataset_type",
    "available_options": ["boot-time-verbose"]
  }
}
```

### Source-Driven Mode Tests

These tests require both RHIVOS PerfScale MCP and Horreum MCP containers running.

#### Test 4: Valid Source-Driven Query

```bash
curl -s -w "\nHTTP Status: %{http_code}\n" -X POST \
  -H 'Authorization: Bearer domain-token' \
  -H 'Content-Type: application/json' \
  http://localhost:8080/tools/get_key_metrics \
  -d '{
    "dataset_types": ["boot-time-verbose"],
    "source_id": "horreum-test",
    "test_id": "boot-test-123",
    "limit": 5
  }'
```

**Expected Result:**
- HTTP Status: 502 (upstream connection issue - expected with fake Horreum instance)
- JSON response with structured error:
```json
{
  "detail": {
    "detail": "Upstream error 404",
    "error_type": "upstream_http_error",
    "available_options": null
  }
}
```

#### Test 5: Invalid Source ID

```bash
curl -s -w "\nHTTP Status: %{http_code}\n" -X POST \
  -H 'Authorization: Bearer domain-token' \
  -H 'Content-Type: application/json' \
  http://localhost:8080/tools/get_key_metrics \
  -d '{
    "dataset_types": ["boot-time-verbose"],
    "source_id": "nonexistent-source",
    "test_id": "test-123",
    "limit": 5
  }'
```

**Expected Result:**
- HTTP Status: 404
- JSON response:
```json
{
  "detail": {
    "detail": "Source ID 'nonexistent-source' not found. Check your DOMAIN_MCP_CONFIG.",
    "error_type": "unknown_source_id",
    "available_options": ["horreum-test"]
  }
}
```

### Error Handling Tests

These tests validate proper HTTP status codes and structured error responses.

#### Test 6: Malformed JSON

```bash
curl -s -w "\nHTTP Status: %{http_code}\n" -X POST \
  -H 'Authorization: Bearer example-domain-token-12345' \
  -H 'Content-Type: application/json' \
  http://localhost:8080/tools/get_key_metrics_raw \
  -d '{"invalid": json}'
```

**Expected Result:**
- HTTP Status: 400
- JSON response with validation error

#### Test 7: Missing Content-Type

```bash
curl -s -w "\nHTTP Status: %{http_code}\n" -X POST \
  -H 'Authorization: Bearer example-domain-token-12345' \
  http://localhost:8080/tools/get_key_metrics_raw \
  -d '{"dataset_types": ["boot-time-verbose"], "data": []}'
```

**Expected Result:**
- HTTP Status: 400
- JSON response indicating input validation error

#### Test 8: Wrong HTTP Method

```bash
curl -s -w "\nHTTP Status: %{http_code}\n" -X GET \
  -H 'Authorization: Bearer example-domain-token-12345' \
  http://localhost:8080/tools/get_key_metrics_raw
```

**Expected Result:**
- HTTP Status: 405
- JSON response:
```json
{
  "detail": {
    "detail": "Method Not Allowed",
    "error_type": "http_error",
    "available_options": null
  }
}
```

### Authentication Tests

#### Test 9: No Authorization Header

```bash
curl -s -w "\nHTTP Status: %{http_code}\n" -X POST \
  -H 'Content-Type: application/json' \
  http://localhost:8080/tools/get_key_metrics_raw \
  -d '{}'
```

**Expected Result:**
- HTTP Status: 401
- JSON response:
```json
{
  "detail": {
    "detail": "Unauthorized",
    "error_type": "http_error",
    "available_options": null
  }
}
```

#### Test 10: Invalid Token

```bash
curl -s -w "\nHTTP Status: %{http_code}\n" -X POST \
  -H 'Authorization: Bearer wrong-token' \
  -H 'Content-Type: application/json' \
  http://localhost:8080/tools/get_key_metrics_raw \
  -d '{}'
```

**Expected Result:**
- HTTP Status: 403
- JSON response:
```json
{
  "detail": {
    "detail": "Forbidden",
    "error_type": "http_error",
    "available_options": null
  }
}
```

### Logging Validation

#### Test 11: Startup Diagnostics

Check that your server provides comprehensive startup logging:

```bash
podman logs rhivos-perfscale-mcp-test | head -20
```

**Expected Log Messages:**
```
INFO src.server.http - http.startup.settings
INFO src.server.http - http.startup.container
INFO src.server.http - http.startup.capabilities
INFO src.domain.plugins - Plugins loaded: 'boot-time-verbose' (1 KPIs)
  - Available dataset types: ['boot-time-verbose']
  - Total plugins: 1
INFO src.domain.plugins - Registered plugin: 'boot-time-verbose' (KPIs: boot.time.total_ms)
INFO src.adapters - External MCP server connections configured: 'horreum-test' (HTTP)
  - ✅ Raw mode: Available
  - ✅ Source-driven mode: Available
```

#### Test 12: Request Logging

After running several test requests, check request logging:

```bash
podman logs rhivos-perfscale-mcp-test --tail 10
```

**Expected Log Patterns:**
```
INFO:     127.0.0.1:xxxxx - "POST /tools/get_key_metrics_raw HTTP/1.1" 200 OK
INFO src.server.http - http.get_key_metrics_raw.success
INFO httpx - HTTP Request: POST http://127.0.0.1:3001/tools/datasets.search "HTTP/1.1 404 Not Found"
```

## Integration Testing

### Full Integration Test Script

Create a comprehensive test script:

```bash
#!/bin/bash
# integration-test.sh

set -e

echo "🚀 Starting RHIVOS PerfScale MCP Integration Tests"

# Function to check HTTP response
check_response() {
    local url="$1"
    local expected_status="$2"
    local description="$3"
    
    echo -n "Testing $description... "
    status=$(curl -s -w "%{http_code}" -o /tmp/response "$url")
    
    if [ "$status" = "$expected_status" ]; then
        echo "✅ PASS (HTTP $status)"
    else
        echo "❌ FAIL (Expected HTTP $expected_status, got $status)"
        cat /tmp/response
        exit 1
    fi
}

# Test health endpoints
check_response "http://localhost:8080/health" "200" "Health endpoint"
check_response "http://localhost:8080/ready" "200" "Ready endpoint"

# Test authentication
check_response "http://localhost:8080/tools/get_key_metrics_raw" "401" "Unauthorized access"

echo "🎉 All integration tests passed!"
```

## Troubleshooting

### Common Issues and Solutions

#### Plugin Registration Issues

**Symptom:** `KeyError: 'boot-time-verbose'`
**Solution:** Check startup logs for plugin registration messages. Restart container if needed.

```bash
podman logs rhivos-perfscale-mcp-test | grep -i plugin
```

#### Configuration Loading Issues

**Symptom:** `source_id not found` or no external MCP connections
**Solution:** Verify configuration file is properly mounted and parsed:

```bash
# Check config file in container
podman exec rhivos-perfscale-mcp-test cat /config/config.json

# Check startup logs for configuration messages
podman logs rhivos-perfscale-mcp-test | grep -i -E "(config|adapter|source)"
```

#### Network Connectivity Issues

**Symptom:** Connection refused or timeout errors
**Solution:** Ensure containers can communicate:

```bash
# Test container-to-container connectivity
podman exec rhivos-perfscale-mcp-test curl -s http://127.0.0.1:3001/health

# Or use host networking
podman run --network host ...
```

#### Authentication Issues

**Symptom:** 401/403 errors when they shouldn't occur
**Solution:** Check token configuration:

```bash
# Verify environment variables
podman exec rhivos-perfscale-mcp-test env | grep DOMAIN_MCP_HTTP_TOKEN
```

### Expected vs Actual Behavior

| Test Scenario | Expected HTTP Status | Expected Response Format |
|---------------|---------------------|---------------------------|
| Valid request | 200 | `{"metric_points": [], "domain_model_version": "1.0.0"}` |
| Invalid dataset type | 400 | `{"detail": {...}, "error_type": "unknown_dataset_type", "available_options": [...]}` |
| Missing auth | 401 | `{"detail": {...}, "error_type": "http_error"}` |
| Invalid token | 403 | `{"detail": {...}, "error_type": "http_error"}` |
| Invalid source_id | 404 | `{"detail": {...}, "error_type": "unknown_source_id", "available_options": [...]}` |
| Wrong HTTP method | 405 | `{"detail": {...}, "error_type": "http_error"}` |
| Upstream error | 502 | `{"detail": {...}, "error_type": "upstream_http_error"}` |

### Cleanup

After testing, clean up your containers:

```bash
# Stop and remove containers
podman stop horreum-mcp-test rhivos-perfscale-mcp-test 2>/dev/null || true
podman rm horreum-mcp-test rhivos-perfscale-mcp-test 2>/dev/null || true

# Remove test configuration file
rm -f test-config.json
```

## Automated Testing

For CI/CD environments, consider creating automated test suites using these patterns:

```bash
# Example pytest integration
def test_domain_mcp_health():
    response = requests.get("http://localhost:8080/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_plugin_registration():
    response = requests.post(
        "http://localhost:8080/tools/get_key_metrics_raw",
        headers={"Authorization": "Bearer example-domain-token-12345"},
        json={
            "dataset_types": ["invalid-type"],
            "data": [{"test": "data"}]
        }
    )
    assert response.status_code == 400
    data = response.json()
    assert "boot-time-verbose" in data["detail"]["available_options"]
```

This testing guide ensures your Domain MCP server deployment is working correctly and helps identify any issues early in development or deployment processes.
