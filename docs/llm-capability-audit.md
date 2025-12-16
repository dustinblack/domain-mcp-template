# LLM Capability Audit: Unexposed Infrastructure

**Date**: 2025-11-04  
**Status**: Active audit  
**Purpose**: Identify capabilities supported by underlying infrastructure but not exposed to LLM clients

---

## Executive Summary

**Critical Finding**: Multiple advanced filtering and control parameters are supported by the Horreum adapter and Source MCP contract but are NOT exposed through the Domain MCP `get_key_metrics` tool to LLM clients.

**Impact**: LLM clients are limited to basic queries and cannot leverage advanced filtering, metric selection, or data source control that the infrastructure already supports.

**Recommendation**: Carefully expose parameters that add value for LLM queries without overwhelming the tool interface.

---

## ✅ Recently Fixed

### 1. `run_id` Parameter (Fixed 2025-11-04)
- **Status**: ✅ RESOLVED
- **What was missing**: Run ID queries were fully supported in `app.py:prefer_label_values_when_available()` but not exposed to LLM
- **Impact**: Users couldn't query specific test runs by Horreum run ID
- **Resolution**: 
  - Added `run_id` to `GetKeyMetricsRequest` model
  - Added to parameter normalization (runId, run → run_id)
  - Updated LLM tool schemas
  - Updated HTTP endpoint descriptions

---

## ⚠️ Currently Missing from LLM

### 2. `merge_strategy` Parameter

**Priority**: MODERATE  
**Complexity**: Medium  
**Value**: High for power users

**What it does**:
Controls how Domain MCP combines data from label values (fast, pre-aggregated) and datasets (slow, complete).

**Supported values**:
- `prefer_fast` (default): Try labels first, fallback to datasets if empty
- `comprehensive`: Fetch both labels AND datasets, merge results
- `labels_only`: Only use labels, fail if unavailable
- `datasets_only`: Skip labels, go straight to datasets

**Code support**:
```python
# src/server/models.py:95-104
merge_strategy: MergeStrategy = Field(
    default=MergeStrategy.PREFER_FAST,
    description=(
        "Data source merging strategy. Controls how the server retrieves and "
        "combines data from multiple sources (label values, datasets). "
        ...
    ),
)
```

**Why expose it**:
- ✅ Users experiencing incomplete label values could request comprehensive mode
- ✅ Power users wanting only fast path could specify labels_only
- ✅ Debugging queries could force dataset path with datasets_only
- ✅ Performance-sensitive queries could explicitly choose prefer_fast

**Why NOT expose it**:
- ❌ Adds complexity to tool interface
- ❌ Most users don't need to know about data sources
- ❌ Default (prefer_fast) works well for 95% of queries

**Recommendation**: 
**EXPOSE WITH GUIDANCE** - Add to advanced parameters section with clear use case examples. Most users won't need it, but power users will appreciate control.

**Implementation**:
```python
# Add to tool schema in src/llm/tool_schemas.py:
**Advanced Parameters** (rarely needed):
- `merge_strategy` (string): Control data source selection
  - "prefer_fast" (default): Fast labels, fallback to datasets
  - "comprehensive": Fetch both sources, merge (slower but complete)
  - "labels_only": Only pre-aggregated data (fail if unavailable)
  - "datasets_only": Skip labels, parse raw datasets (slowest)
  - Use "comprehensive" if results seem incomplete
```

---

### 3. `schema_uri` Parameter

**Priority**: LOW  
**Complexity**: Low  
**Value**: Low for typical queries

**What it does**:
Filters datasets by specific schema URI (e.g., `urn:horreum:boot-time:1.0`).

**Code support**:
```python
# src/server/models.py:66-68
schema_uri: str = Field(
    default="",
    description="Optional dataset schema filter.",
)
```

**Why expose it**:
- ✅ Technical users could filter by schema version
- ✅ Useful for schema evolution queries ("show data from old schema vs new")

**Why NOT expose it**:
- ❌ Very technical, not intuitive for natural language
- ❌ Most users don't know schema URIs
- ❌ Auto-discovery works without it

**Recommendation**: 
**DO NOT EXPOSE** - Too technical, minimal value for LLM queries. Keep for HTTP API only.

---

### 4. Advanced Label Value Filtering (CRITICAL GAP!)

**Priority**: HIGH  
**Complexity**: High  
**Value**: Very High

**What's missing**:
The Horreum adapter's `TestLabelValuesRequest` supports powerful filtering parameters that are NOT passed through Domain MCP:

```python
# src/schemas/source_mcp_contract.py:442-489
class TestLabelValuesRequest(BaseModel):
    test_id: str
    include: List[str] = Field(default_factory=list)  # ❌ NOT EXPOSED
    exclude: List[str] = Field(default_factory=list)  # ❌ NOT EXPOSED
    filter: Optional[Dict[str, Any]] = None           # ❌ NOT EXPOSED
    multi_filter: bool = False                         # ✅ USED INTERNALLY
    filtering: bool = False                            # ✅ USED INTERNALLY
    metrics: bool = True                               # ✅ USED INTERNALLY
    before: Optional[str] = None                       # ✅ MAPPED (to_timestamp)
    after: Optional[str] = None                        # ✅ MAPPED (from_timestamp)
    sort: Optional[str] = None                         # ❌ NOT EXPOSED
    direction: Optional[str] = None                    # ❌ NOT EXPOSED
    page_size: int = 100                               # ✅ MAPPED (limit)
```

**Architecture issue**:
Domain MCP's `prefer_label_values_when_available()` only accepts:
- `test_id`, `run_id`, `source_id`
- `before`, `after`, `page_size`
- `os_filter`, `run_type_filter` (internal)

But Horreum supports much more!

**Missing capabilities**:

#### 4a. `include` / `exclude` Parameters
- **What**: Include/exclude specific label names
- **Use case**: "Show only kernel and initrd boot phases" or "Exclude confidence intervals"
- **Example**: `include=["BOOT2 - Kernel Post-Timer Duration Average ms"]`
- **Impact**: Reduces data transfer, focuses queries
- **Recommendation**: **EXPOSE** - Very useful for optimizing queries

#### 4b. `filter` Parameter (JSON Filter Expression)
- **What**: Complex JSON filtering on label values
- **Use case**: "Show runs where boot time > 5000ms"
- **Example**: `filter={"Boot Time": {">": 5000}}`
- **Impact**: Server-side filtering reduces data transfer
- **Recommendation**: **EVALUATE** - Powerful but complex for LLM to construct

#### 4c. `sort` / `direction` Parameters
- **What**: Sort results by specific fields
- **Use case**: "Show slowest boot times first"
- **Example**: `sort="Boot Time", direction="desc"`
- **Impact**: Results pre-sorted, easier for LLM to process
- **Recommendation**: **EXPOSE** - Simple and useful

---

### 5. Multi-Filter Already Used Internally

**Status**: ✅ ALREADY WORKING (just not configurable)

**What it does**:
Enables array-based multi-value filtering in Horreum (e.g., `{"RHIVOS OS ID": ["rhel", "autosd"]}`).

**Current usage**:
- Automatically set to `True` when os_filter or run_type_filter provided
- Hardcoded in `src/server/app.py:192`

**Recommendation**: 
**KEEP INTERNAL** - This is an implementation detail. LLM doesn't need to know about multiFilter vs single filter, just provide `os_id="rhel"` and it works.

---

### 6. `filtering` and `metrics` Booleans

**Status**: ✅ ALREADY OPTIMIZED (hardcoded to correct values)

**What they do**:
- `metrics=True`: Return metric labels (boot times, etc.)
- `filtering=True`: Return dimension labels (os_id, mode, target, etc.)

**Current usage**:
- Hardcoded in `src/server/app.py:172-173`
- Both set to `True` to get all labels (metrics + dimensions)

**Recommendation**: 
**KEEP INTERNAL** - This was set to True after discovering the dimension bug. Always want both, no reason to expose.

---

## 🎯 Recommended Actions

### Immediate (High Priority)

1. **✅ COMPLETED**: Expose `run_id` parameter (done 2025-11-04)

2. **TODO**: Expose `merge_strategy` parameter
   - Add to `GetKeyMetricsRequest` model (already exists)
   - Document in LLM tool schema with use cases
   - Update HTTP endpoint description
   - Target: Phase 3.2 or 3.3

3. **TODO**: Expose `sort` and `direction` parameters
   - Add to `prefer_label_values_when_available()` signature
   - Pass through to Horreum adapter
   - Document in LLM tool schema
   - Target: Phase 3.3

### Short-term (Medium Priority)

4. **TODO**: Expose `include` / `exclude` parameters
   - Add to `prefer_label_values_when_available()` signature
   - Pass through to Horreum adapter
   - Document in LLM tool schema with examples
   - Target: Phase 3.4

### Long-term (Evaluate)

5. **EVALUATE**: JSON `filter` parameter
   - Very powerful but complex for LLM to construct
   - Might be better to add higher-level filters (e.g., `min_boot_time`, `max_boot_time`)
   - Consider for Phase 4+ after evaluating LLM capabilities

6. **SKIP**: `schema_uri` parameter
   - Too technical for natural language queries
   - Keep for HTTP API only

---

## 📊 Impact Assessment

| Parameter | Priority | LLM Value | Implementation Cost | Recommendation |
|-----------|----------|-----------|---------------------|----------------|
| `run_id` | CRITICAL | High | Low | ✅ DONE |
| `merge_strategy` | MODERATE | Medium-High | Low | ✅ DO IT |
| `sort` + `direction` | MODERATE | Medium | Low | ✅ DO IT |
| `include` / `exclude` | MODERATE | High | Medium | ✅ DO IT |
| `filter` (JSON) | LOW | High (if done right) | High | ⏸️ EVALUATE |
| `schema_uri` | LOW | Very Low | Low | ❌ SKIP |
| `multi_filter` | N/A | N/A | N/A | ✅ KEEP INTERNAL |
| `filtering` + `metrics` | N/A | N/A | N/A | ✅ KEEP INTERNAL |

---

## 🔍 How This Was Discovered

This audit was triggered by discovering that `run_id` was fully supported in the code but not exposed to the LLM. This led to a systematic review of:

1. ✅ `GetKeyMetricsRequest` model fields
2. ✅ `prefer_label_values_when_available()` parameters
3. ✅ `TestLabelValuesRequest` Horreum contract
4. ✅ `RunLabelValuesRequest` Horreum contract
5. ✅ Parameter normalization logic
6. ✅ LLM tool schema documentation

**Key insight**: The Horreum adapter (and Source MCP contract) support much richer filtering than Domain MCP exposes. This is by design (simplicity) but some capabilities would genuinely improve LLM queries.

---

## 📝 Implementation Checklist

When exposing new parameters, ensure ALL layers are updated:

- [ ] Add to `GetKeyMetricsRequest` Pydantic model
- [ ] Add to parameter normalization (handle synonyms, type coercion)
- [ ] Add to `prefer_label_values_when_available()` signature
- [ ] Pass through in `_fetch_from_sources()`
- [ ] Pass through in `_call_get_key_metrics()`
- [ ] Add to LLM tool schema with examples
- [ ] Add to HTTP `/tools/get_key_metrics` OpenAPI description
- [ ] Add to `/api/query` handler docstring
- [ ] Update query-failures.md if related to past issues
- [ ] Add integration tests
- [ ] Update domain glossary if domain-specific

---

## Related Documents

- `docs/query-failures.md` - Track user queries that failed due to missing capabilities
- `domain_mcp_development_plan.md` - Development phases and priorities
- `docs/contracts/source-mcp-contract.md` - Full Horreum contract specification
- `src/schemas/source_mcp_contract.py` - Code-first contract schemas

---

**AI-assisted-by**: Claude Sonnet 4.5  
**Last Updated**: 2025-11-04

