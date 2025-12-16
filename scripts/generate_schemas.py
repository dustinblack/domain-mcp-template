#!/usr/bin/env python3
"""
Generate JSON Schemas and Documentation from Pydantic Models

This script generates:
1. JSON Schema files for each contract operation
2. OpenAPI specification 
3. Markdown documentation
4. Test fixtures

Usage:
    python scripts/generate_schemas.py [--output-dir schemas/] [--format json|yaml|markdown]
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schemas.source_mcp_contract import (
    ArtifactsGetRequest,
    ArtifactsGetResponse,
    ContractVersion,
    DatasetsGetRequest,
    DatasetsGetResponse,
    DatasetsSearchRequest,
    DatasetsSearchResponse,
    ErrorResponse,
    RunsListRequest,
    RunsListResponse,
    SchemasGetRequest,
    SchemasGetResponse,
    SourceDescribeRequest,
    SourceDescribeResponse,
    TestsListRequest,
    TestsListResponse,
)


def generate_json_schemas(output_dir: Path) -> None:
    """Generate JSON Schema files for all contract operations"""

    schemas = {
        # source.describe
        "source_describe_request": SourceDescribeRequest.model_json_schema(),
        "source_describe_response": SourceDescribeResponse.model_json_schema(),
        # tests.list
        "tests_list_request": TestsListRequest.model_json_schema(),
        "tests_list_response": TestsListResponse.model_json_schema(),
        # runs.list
        "runs_list_request": RunsListRequest.model_json_schema(),
        "runs_list_response": RunsListResponse.model_json_schema(),
        # datasets.search
        "datasets_search_request": DatasetsSearchRequest.model_json_schema(),
        "datasets_search_response": DatasetsSearchResponse.model_json_schema(),
        # datasets.get
        "datasets_get_request": DatasetsGetRequest.model_json_schema(),
        "datasets_get_response": DatasetsGetResponse.model_json_schema(),
        # artifacts.get
        "artifacts_get_request": ArtifactsGetRequest.model_json_schema(),
        "artifacts_get_response": ArtifactsGetResponse.model_json_schema(),
        # schemas.get
        "schemas_get_request": SchemasGetRequest.model_json_schema(),
        "schemas_get_response": SchemasGetResponse.model_json_schema(),
        # Common
        "error_response": ErrorResponse.model_json_schema(),
    }

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write individual schema files
    for name, schema in schemas.items():
        schema_file = output_dir / f"{name}.json"
        with open(schema_file, "w") as f:
            json.dump(schema, f, indent=2)
        print(f"Generated: {schema_file}")

    # Write combined schema file
    combined_file = output_dir / "source_mcp_contract_schemas.json"
    with open(combined_file, "w") as f:
        json.dump(
            {"contract_version": ContractVersion.V1_0_0, "schemas": schemas},
            f,
            indent=2,
        )
    print(f"Generated: {combined_file}")


def generate_markdown_docs(output_dir: Path) -> None:
    """Generate markdown documentation from schemas"""

    docs_dir = output_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    # Generate contract documentation
    contract_doc = docs_dir / "source_mcp_contract.md"

    with open(contract_doc, "w") as f:
        f.write(
            f"""# Source MCP Contract v{ContractVersion.V1_0_0}

**Generated from code** - Do not edit manually.

This document is automatically generated from the Pydantic schema definitions 
in `src/schemas/source_mcp_contract.py`. 

## Overview

The Source MCP Contract defines a minimal, versioned tool schema that any 
backend can implement to provide data to the Domain MCP.

## Schema Validation

All schemas are defined as Pydantic models with runtime validation. The JSON 
Schema definitions are generated automatically and kept in sync with the code.

## Contract Operations

### 1. source.describe

Returns metadata about the source implementation.

**Request Schema**: See `source_describe_request.json`
**Response Schema**: See `source_describe_response.json`

### 2. tests.list

Lists available tests with optional filtering.

**Request Schema**: See `tests_list_request.json`  
**Response Schema**: See `tests_list_response.json`

### 3. runs.list

Lists test runs for a specific test.

**Request Schema**: See `runs_list_request.json`
**Response Schema**: See `runs_list_response.json`

### 4. datasets.search

Searches for datasets across tests and runs.

**Request Schema**: See `datasets_search_request.json`
**Response Schema**: See `datasets_search_response.json`

### 5. datasets.get

Retrieves the raw content of a specific dataset.

**Request Schema**: See `datasets_get_request.json`
**Response Schema**: See `datasets_get_response.json`

### 6. artifacts.get

Retrieves binary artifacts associated with a test run.

**Request Schema**: See `artifacts_get_request.json`
**Response Schema**: See `artifacts_get_response.json`

### 7. schemas.get (Optional)

Retrieves schema definitions for datasets.

**Request Schema**: See `schemas_get_request.json`
**Response Schema**: See `schemas_get_response.json`

## Error Handling

All operations return errors in the standardized format defined in `error_response.json`.

## Implementation

To implement a Source MCP:

1. Import the schema models: `from schemas.source_mcp_contract import *`
2. Use the Pydantic models for request/response validation
3. Implement each contract operation with proper error handling
4. Test against the generated JSON schemas

## Schema Generation

Schemas are generated using:

```bash
python scripts/generate_schemas.py --output-dir schemas/
```

This ensures schemas stay in sync with the code definitions.
"""
        )

    print(f"Generated: {contract_doc}")


def generate_test_fixtures(output_dir: Path) -> None:
    """Generate test fixture examples"""

    fixtures_dir = output_dir / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    # Example source.describe response
    describe_example = {
        "source_type": "horreum",
        "version": "1.2.0",
        "contract_version": "1.0.0",
        "capabilities": {
            "pagination": True,
            "caching": True,
            "streaming": False,
            "schemas": True,
        },
        "limits": {
            "max_page_size": 1000,
            "max_dataset_size": 104857600,
            "rate_limit_per_minute": 100,
        },
    }

    with open(fixtures_dir / "source_describe_response.json", "w") as f:
        json.dump(describe_example, f, indent=2)

    # Example tests.list response
    tests_example = {
        "tests": [
            {
                "test_id": "262",
                "name": "boot-time-verbose",
                "description": "Verbose boot time measurements",
                "tags": ["boot-time", "performance", "rhivos"],
                "created_at": "2025-01-01T00:00:00Z",
            }
        ],
        "pagination": {"has_more": False, "total_count": 1},
    }

    with open(fixtures_dir / "tests_list_response.json", "w") as f:
        json.dump(tests_example, f, indent=2)

    print(f"Generated test fixtures in: {fixtures_dir}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate schemas from Pydantic models"
    )
    parser.add_argument("--output-dir", default="schemas", help="Output directory")
    parser.add_argument(
        "--format",
        choices=["json", "markdown", "all"],
        default="all",
        help="Output format",
    )

    args = parser.parse_args()
    output_dir = Path(args.output_dir)

    if args.format in ["json", "all"]:
        generate_json_schemas(output_dir)

    if args.format in ["markdown", "all"]:
        generate_markdown_docs(output_dir)

    if args.format in ["all"]:
        generate_test_fixtures(output_dir)

    print(f"\nSchema generation complete! Output in: {output_dir}")
    print("\nTo use these schemas:")
    print("1. Import models: from schemas.source_mcp_contract import *")
    print("2. Validate requests: request = TestsListRequest(**data)")
    print("3. Generate responses: response = TestsListResponse(...)")
    print("4. Test with fixtures: Load JSON from fixtures/ directory")


if __name__ == "__main__":
    main()
