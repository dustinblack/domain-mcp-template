#!/bin/bash
# quick-validate.sh - Simple validation script for Domain MCP server
# Usage: ./scripts/quick-validate.sh [BASE_URL] [AUTH_TOKEN]

BASE_URL="${1:-http://localhost:8080}"
AUTH_TOKEN="${2:-test-token}"

echo "🚀 Domain MCP Quick Validation"
echo "Base URL: $BASE_URL"
echo "Auth Token: ${AUTH_TOKEN:0:8}***"
echo

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

PASSED=0
FAILED=0

test_endpoint() {
    local name="$1"
    local url="$2"
    local expected_status="$3"
    local auth="$4"
    
    echo -n "Testing $name... "
    
    if [ "$auth" = "true" ]; then
        status=$(curl -s -w "%{http_code}" -o /dev/null -H "Authorization: Bearer $AUTH_TOKEN" "$url")
    else
        status=$(curl -s -w "%{http_code}" -o /dev/null "$url")
    fi
    
    if [ "$status" = "$expected_status" ]; then
        echo -e "${GREEN}✅ PASS (HTTP $status)${NC}"
        ((PASSED++))
    else
        echo -e "${RED}❌ FAIL (Expected $expected_status, got $status)${NC}"
        ((FAILED++))
    fi
}

test_json_endpoint() {
    local name="$1"
    local url="$2"
    local data="$3"
    local expected_status="$4"
    local use_auth="${5:-true}"
    
    echo -n "Testing $name... "
    
    if [ "$use_auth" = "true" ]; then
        status=$(curl -s -w "%{http_code}" -o /tmp/response.json \
            -X POST \
            -H "Authorization: Bearer $AUTH_TOKEN" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$url")
    else
        status=$(curl -s -w "%{http_code}" -o /tmp/response.json \
            -X POST \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$url")
    fi
    
    if [ "$status" = "$expected_status" ]; then
        echo -e "${GREEN}✅ PASS (HTTP $status)${NC}"
        ((PASSED++))
    else
        echo -e "${RED}❌ FAIL (Expected $expected_status, got $status)${NC}"
        ((FAILED++))
        echo "Response: $(cat /tmp/response.json 2>/dev/null || echo 'No response')"
    fi
}

# Run tests
test_endpoint "Health endpoint" "$BASE_URL/health" "200" "false"
test_endpoint "Ready endpoint" "$BASE_URL/ready" "200" "false"
test_json_endpoint "Unauthorized access" "$BASE_URL/tools/get_key_metrics_raw" \
    '{"dataset_types": ["boot-time-verbose"], "data": []}' \
    "401" "false"

test_json_endpoint "Valid raw request" "$BASE_URL/tools/get_key_metrics_raw" \
    '{"dataset_types": ["boot-time-verbose"], "data": [{"$schema": "urn:boot-time-verbose:04", "test_results": []}]}' \
    "200"

test_json_endpoint "Invalid dataset type" "$BASE_URL/tools/get_key_metrics_raw" \
    '{"dataset_types": ["invalid-type"], "data": [{"test": "data"}]}' \
    "400"

# Summary
echo
echo "📊 Results: $PASSED passed, $FAILED failed"

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed.${NC}"
    exit 1
fi
