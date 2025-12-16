# Source MCP Contract Specification

## Overview

This document defines the Source MCP Contract - a minimal, versioned tool schema 
that any backend can implement to provide data to domain-specific MCP servers. This contract 
is designed to be backend-agnostic and focuses on the essential operations 
needed for domain-specific analysis.

## ⚠️ Schema Definition Approach

**Code-First Schemas**: The authoritative schema definitions are maintained as 
Pydantic models in [`src/schemas/source_mcp_contract.py`](../../src/schemas/source_mcp_contract.py). 

**Why Code-First?**:
- ✅ **No Drift**: Schemas are validated at runtime and used in implementation
- ✅ **Single Source of Truth**: Code is the specification
- ✅ **Auto-Generation**: JSON schemas and docs generated from code
- ✅ **Type Safety**: Full IDE support and static analysis
- ✅ **Testing**: Schemas are directly testable

**Generate Schemas**: Run `python scripts/generate_schemas.py` to create JSON 
Schema files and updated documentation.

## Contract Version

- **Version**: `1.0.0`
- **Compatibility**: Semantic versioning with backward compatibility guarantees

## Core Principles

1. **Backend Agnostic**: Works with Horreum or any other data source backend
2. **Minimal Surface**: Only essential operations for domain analysis
3. **Pagination First**: All list operations support consistent pagination
4. **Cache Friendly**: Includes ETags and conditional request support
5. **Error Resilient**: Structured errors with retry hints
6. **Language Neutral**: snake_case naming for cross-language compatibility

## Naming Conventions

**Contract Standard**: Use `snake_case` for all parameter names to ensure compatibility across Python, JavaScript, and other languages.

**Implementation Note for Python/JavaScript Interop**:
- The Source MCP Contract uses `snake_case` as the canonical standard (e.g., `test_id`, `run_id`, `filter`)
- As of 2025-10-15, the Horreum MCP backend accepts BOTH `snake_case` and `camelCase` universally for all parameters
- Python implementations SHOULD use Pydantic field aliases to document cross-language boundaries and send canonical JavaScript conventions (`camelCase`) downstream

Example: Parameters use aliases for bidirectional flexibility and clear documentation:
```python
class TestLabelValuesRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)  # Accept both forms
    
    multi_filter: bool = Field(
        default=False, 
        alias="multiFilter",  # Send camelCase to JavaScript services
        description="Enable array multi-value filtering",
    )
```

**Benefits**:
- Clients can use either naming convention (`multi_filter` OR `multiFilter`)
- Domain MCP sends canonical JavaScript forms downstream for consistency
- Explicit documentation of Python/JavaScript boundaries in code
- Backward compatible with services that only support one convention
- Defense in depth if downstream services have different requirements

See **[Python/JavaScript Interop](../DEVELOPERS.md#pythonjavascript-interop)** for complete technical details and historical context.

## Tool Definitions

### 1. source.describe

Returns metadata about the source implementation.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "sourceType": {
      "type": "string",
        "description": "Backend type identifier",
        "examples": ["horreum", "custom-backend", "data-warehouse"]
    },
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+$",
      "description": "Source MCP implementation version"
    },
    "contractVersion": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+$",
      "description": "Source MCP Contract version supported"
    },
    "capabilities": {
      "type": "object",
      "properties": {
        "pagination": {"type": "boolean"},
        "caching": {"type": "boolean"},
        "streaming": {"type": "boolean"},
        "schemas": {"type": "boolean"}
      },
      "required": ["pagination", "caching"]
    },
    "limits": {
      "type": "object",
      "properties": {
        "maxPageSize": {"type": "integer", "minimum": 1},
        "maxDatasetSize": {"type": "integer", "minimum": 1},
        "rateLimitPerMinute": {"type": "integer", "minimum": 1}
      }
    }
  },
  "required": ["sourceType", "version", "contractVersion", "capabilities"]
}
```

### 2. tests.list

Lists available tests with optional filtering.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Text search query for test names/descriptions"
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Filter by test tags"
    },
    "pageToken": {
      "type": "string",
      "description": "Opaque pagination token"
    },
    "pageSize": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000,
      "default": 100,
      "description": "Number of items per page"
    }
  },
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "tests": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "testId": {"type": "string"},
          "name": {"type": "string"},
          "description": {"type": "string"},
          "tags": {
            "type": "array",
            "items": {"type": "string"}
          },
          "createdAt": {
            "type": "string",
            "format": "date-time"
          },
          "updatedAt": {
            "type": "string",
            "format": "date-time"
          }
        },
        "required": ["testId", "name"]
      }
    },
    "pagination": {
      "type": "object",
      "properties": {
        "nextPageToken": {"type": "string"},
        "hasMore": {"type": "boolean"},
        "totalCount": {"type": "integer", "minimum": 0}
      },
      "required": ["hasMore"]
    },
    "cacheInfo": {
      "type": "object",
      "properties": {
        "etag": {"type": "string"},
        "lastModified": {"type": "string", "format": "date-time"},
        "maxAge": {"type": "integer", "minimum": 0}
      }
    }
  },
  "required": ["tests", "pagination"]
}
```

### 3. runs.list

Lists test runs for a specific test.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "testId": {
      "type": "string",
      "description": "Test identifier to list runs for"
    },
    "from": {
      "type": "string",
      "format": "date-time",
      "description": "Start of time range filter"
    },
    "to": {
      "type": "string",
      "format": "date-time", 
      "description": "End of time range filter"
    },
    "pageToken": {
      "type": "string",
      "description": "Opaque pagination token"
    },
    "pageSize": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000,
      "default": 100,
      "description": "Number of items per page"
    }
  },
  "required": ["testId"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "runs": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "runId": {"type": "string"},
          "testId": {"type": "string"},
          "startedAt": {
            "type": "string",
            "format": "date-time"
          },
          "completedAt": {
            "type": "string",
            "format": "date-time"
          },
          "status": {
            "type": "string",
            "enum": ["running", "completed", "failed", "cancelled"]
          },
          "labels": {
            "type": "object",
            "additionalProperties": {"type": "string"}
          },
          "metadata": {
            "type": "object",
            "additionalProperties": true
          }
        },
        "required": ["runId", "testId", "startedAt", "status"]
      }
    },
    "pagination": {
      "type": "object", 
      "properties": {
        "nextPageToken": {"type": "string"},
        "hasMore": {"type": "boolean"},
        "totalCount": {"type": "integer", "minimum": 0}
      },
      "required": ["hasMore"]
    },
    "cacheInfo": {
      "type": "object",
      "properties": {
        "etag": {"type": "string"},
        "lastModified": {"type": "string", "format": "date-time"},
        "maxAge": {"type": "integer", "minimum": 0}
      }
    }
  },
  "required": ["runs", "pagination"]
}
```

### 4. datasets.search

Searches for datasets across tests and runs.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "testId": {
      "type": "string",
      "description": "Filter by specific test"
    },
    "schemaUri": {
      "type": "string",
      "description": "Filter by dataset schema URI"
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Filter by dataset tags"
    },
    "runIds": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Filter by specific run IDs"
    },
    "from": {
      "type": "string",
      "format": "date-time",
      "description": "Start of time range filter"
    },
    "to": {
      "type": "string", 
      "format": "date-time",
      "description": "End of time range filter"
    },
    "pageToken": {
      "type": "string",
      "description": "Opaque pagination token"
    },
    "pageSize": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000,
      "default": 100,
      "description": "Number of items per page"
    }
  },
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "datasets": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "datasetId": {"type": "string"},
          "runId": {"type": "string"},
          "testId": {"type": "string"},
          "schemaUri": {"type": "string"},
          "name": {"type": "string"},
          "description": {"type": "string"},
          "tags": {
            "type": "array",
            "items": {"type": "string"}
          },
          "createdAt": {
            "type": "string",
            "format": "date-time"
          },
          "sizeBytes": {
            "type": "integer",
            "minimum": 0
          },
          "contentType": {
            "type": "string",
            "default": "application/json"
          }
        },
        "required": ["datasetId", "runId", "testId"]
      }
    },
    "pagination": {
      "type": "object",
      "properties": {
        "nextPageToken": {"type": "string"},
        "hasMore": {"type": "boolean"},
        "totalCount": {"type": "integer", "minimum": 0}
      },
      "required": ["hasMore"]
    },
    "cacheInfo": {
      "type": "object",
      "properties": {
        "etag": {"type": "string"},
        "lastModified": {"type": "string", "format": "date-time"},
        "maxAge": {"type": "integer", "minimum": 0}
      }
    }
  },
  "required": ["datasets", "pagination"]
}
```

### 5. datasets.get

Retrieves the raw content of a specific dataset.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "datasetId": {
      "type": "string",
      "description": "Dataset identifier to retrieve"
    },
    "ifNoneMatch": {
      "type": "string",
      "description": "ETag for conditional request"
    },
    "ifModifiedSince": {
      "type": "string",
      "format": "date-time",
      "description": "Timestamp for conditional request"
    }
  },
  "required": ["datasetId"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "datasetId": {"type": "string"},
    "content": {
      "description": "Raw dataset content as JSON object or string"
    },
    "contentType": {
      "type": "string",
      "default": "application/json"
    },
    "sizeBytes": {
      "type": "integer",
      "minimum": 0
    },
    "cacheInfo": {
      "type": "object",
      "properties": {
        "etag": {"type": "string"},
        "lastModified": {"type": "string", "format": "date-time"},
        "maxAge": {"type": "integer", "minimum": 0}
      }
    },
    "metadata": {
      "type": "object",
      "properties": {
        "schemaUri": {"type": "string"},
        "encoding": {"type": "string"},
        "compression": {"type": "string"}
      }
    }
  },
  "required": ["datasetId", "content"]
}
```

### 6. artifacts.get

Retrieves binary artifacts associated with a test run.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "runId": {
      "type": "string",
      "description": "Run identifier"
    },
    "name": {
      "type": "string",
      "description": "Artifact name/path"
    },
    "ifNoneMatch": {
      "type": "string",
      "description": "ETag for conditional request"
    },
    "ifModifiedSince": {
      "type": "string",
      "format": "date-time",
      "description": "Timestamp for conditional request"
    }
  },
  "required": ["runId", "name"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "runId": {"type": "string"},
    "name": {"type": "string"},
    "content": {
      "type": "string",
      "description": "Base64 encoded binary content"
    },
    "contentType": {
      "type": "string",
      "description": "MIME type of the artifact"
    },
    "sizeBytes": {
      "type": "integer",
      "minimum": 0
    },
    "cacheInfo": {
      "type": "object",
      "properties": {
        "etag": {"type": "string"},
        "lastModified": {"type": "string", "format": "date-time"},
        "maxAge": {"type": "integer", "minimum": 0}
      }
    }
  },
  "required": ["runId", "name", "content", "contentType"]
}
```

### 7. schemas.get (Optional)

Retrieves schema definitions for datasets.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "schemaUri": {
      "type": "string",
      "description": "Schema URI to retrieve"
    }
  },
  "required": ["schemaUri"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "schemaUri": {"type": "string"},
    "schema": {
      "type": "object",
      "description": "JSON Schema definition"
    },
    "version": {"type": "string"},
    "description": {"type": "string"}
  },
  "required": ["schemaUri", "schema"]
}
```

## Error Response Schema

All tools must return errors in this standardized format:

```json
{
  "type": "object",
  "properties": {
    "error": {
      "type": "object",
      "properties": {
        "code": {
          "type": "string",
          "enum": [
            "INVALID_REQUEST",
            "NOT_FOUND", 
            "RATE_LIMITED",
            "INTERNAL_ERROR",
            "SERVICE_UNAVAILABLE",
            "TIMEOUT"
          ]
        },
        "message": {"type": "string"},
        "details": {
          "type": "object",
          "additionalProperties": true
        },
        "retryAfter": {
          "type": "integer",
          "minimum": 0,
          "description": "Seconds to wait before retry"
        },
        "retryable": {
          "type": "boolean",
          "description": "Whether this error is retryable"
        }
      },
      "required": ["code", "message"]
    }
  },
  "required": ["error"]
}
```

## Implementation Requirements

### Pagination
- Use opaque `pageToken` for stateless pagination
- Maintain consistent ordering across pages
- Support `hasMore` flag for efficient iteration
- Optional `totalCount` for UI purposes

### Caching
- Include ETags for content-based caching
- Support conditional requests (`If-None-Match`, `If-Modified-Since`)
- Provide cache hints (`max-age`) when possible
- Return `304 Not Modified` for unchanged content

### Rate Limiting
- Return `RATE_LIMITED` error with `retryAfter` seconds
- Include rate limit headers when possible
- Implement per-client rate limiting

### Timeouts
- Set reasonable timeouts for all operations
- Return `TIMEOUT` error for operations that exceed limits
- Support partial results when possible

## Compatibility

### Version Negotiation
Clients should check `contractVersion` in `source.describe` response and adapt 
to supported contract versions.

### Backward Compatibility
- New optional fields can be added to responses
- New optional parameters can be added to requests  
- Existing fields cannot be removed or changed in meaning
- Error codes cannot be removed

### Forward Compatibility
- Clients should ignore unknown response fields
- Clients should not send unknown request parameters
- Clients should handle new error codes gracefully

## Testing

### Contract Compliance Tests
Each Source MCP implementation should include:

- Schema validation for all tool inputs/outputs
- Pagination behavior verification
- Caching header validation
- Error response format verification
- Rate limiting behavior tests

### Reference Implementation
The Horreum MCP serves as the reference implementation for this contract.

## Changelog

- **2025-09-22**: Initial contract specification with core tools and schemas
