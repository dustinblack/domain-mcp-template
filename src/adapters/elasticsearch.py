"""Elasticsearch Source MCP adapter.

This adapter translates the Source MCP Contract into calls to an Elasticsearch
MCP server. It maps Domain concepts to Elasticsearch concepts:
- Tests -> Indices
- Datasets -> Documents (Log entries)
- Runs -> Not explicitly mapped (could be trace IDs in future)

This allows the generic Domain MCP orchestration (get_key_metrics) to work
against Elasticsearch data.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .. import __version__
from ..schemas.source_mcp_contract import (
    ArtifactsGetRequest,
    ArtifactsGetResponse,
    ContractVersion,
    DatasetLabelValuesRequest,
    DatasetLabelValuesResponse,
    DatasetsGetRequest,
    DatasetsGetResponse,
    DatasetsSearchRequest,
    DatasetsSearchResponse,
    DatasetInfo,
    RunLabelValuesRequest,
    RunLabelValuesResponse,
    RunsListRequest,
    RunsListResponse,
    SourceCapabilities,
    SourceDescribeRequest,
    SourceDescribeResponse,
    SourceLimits,
    SourceType,
    TestLabelValuesRequest,
    TestLabelValuesResponse,
    TestsListRequest,
    TestsListResponse,
    TestInfo,
    Pagination,
)
from .mcp_bridge import MCPBridgeAdapter

logger = logging.getLogger(__name__)


class ElasticsearchAdapter(MCPBridgeAdapter):
    """Adapter for the Elasticsearch MCP.

    Inherits from MCPBridgeAdapter to reuse the stdio connection logic,
    but overrides the contract methods to map them to Elasticsearch tools.
    """

    async def source_describe(
        self, req: SourceDescribeRequest
    ) -> SourceDescribeResponse:
        """Describe Elasticsearch source capabilities."""
        _ = req
        return SourceDescribeResponse(
            source_type=SourceType.ELASTICSEARCH,
            version=__version__,
            contract_version=ContractVersion.V1_0_0,
            capabilities=SourceCapabilities(
                pagination=True,
                caching=False,
                streaming=False,
                schemas=True
            ),
            limits=SourceLimits(
                max_page_size=1000,
                max_dataset_size=None,
                rate_limit_per_minute=None,
            ),
        )

    async def tests_list(self, req: TestsListRequest) -> TestsListResponse:
        """List Elasticsearch indices as 'Tests'.

        Maps 'query' to index pattern matching.
        """
        pattern = req.query or "*"
        # Call the underlying 'list_indices' tool
        # Note: The actual tool args depend on the elasticsearch-mcp implementation.
        # We assume 'list_indices' takes 'index_pattern' or similar.
        # Checking contract... standard tool is `list_indices(index_pattern: str)`
        
        try:
            result = await self._call("list_indices", {"index_pattern": pattern})
            
            # Result is likely a list of strings or objects.
            # We need to adapt it to TestInfo objects.
            # Assuming result structure: {"indices": ["idx1", "idx2"]} or similar
            # If result is just the list, handle that too.
            
            indices = []
            if isinstance(result, list):
                indices = result
            elif isinstance(result, dict):
                indices = result.get("indices", [])
                if not indices and "items" in result:
                     indices = result.get("items", [])

            tests = []
            for idx in indices:
                # idx might be a string or a dict
                name = idx if isinstance(idx, str) else str(idx.get("name", idx))
                tests.append(
                    TestInfo(
                        test_id=name, # Use index name as ID
                        name=name,
                        description="Elasticsearch Index",
                        tags=["elasticsearch", "index"]
                    )
                )
            
            # Simple pagination slice (since list_indices returns everything usually)
            start = 0
            if req.page_token:
                try:
                    start = int(req.page_token)
                except ValueError:
                    pass
            
            end = start + req.page_size
            page = tests[start:end]
            
            has_more = end < len(tests)
            next_token = str(end) if has_more else None

            return TestsListResponse(
                tests=page,
                pagination=Pagination(
                    has_more=has_more,
                    next_page_token=next_token,
                    total_count=len(tests)
                )
            )

        except Exception as e:
            logger.error(f"Failed to list indices: {e}")
            return TestsListResponse(
                tests=[],
                pagination=Pagination(has_more=False)
            )

    async def runs_list(self, req: RunsListRequest) -> RunsListResponse:
        """List runs. 
        
        Elasticsearch doesn't have inherent 'runs'. We return an empty list 
        or could implement time-window bucketing in the future.
        """
        return RunsListResponse(
            runs=[],
            pagination=Pagination(has_more=False, total_count=0)
        )

    async def datasets_search(
        self, req: DatasetsSearchRequest
    ) -> DatasetsSearchResponse:
        """Search for documents (Datasets) in an Index (Test).

        Maps:
        - test_id -> index
        - from/to -> @timestamp range
        """
        if not req.test_id:
            # Cannot search without an index
            return DatasetsSearchResponse(
                datasets=[],
                pagination=Pagination(has_more=False)
            )

        index = req.test_id
        
        # Build Elasticsearch Query DSL
        # This is a basic implementation; can be expanded
        query_body: Dict[str, Any] = {
            "size": req.page_size,
            "sort": [{"@timestamp": "desc"}],
            "query": {"bool": {"filter": []}}
        }

        # Add time range filter
        if req.from_time or req.to_time:
            range_filter = {"range": {"@timestamp": {}}}
            if req.from_time:
                range_filter["range"]["@timestamp"]["gte"] = req.from_time
            if req.to_time:
                range_filter["range"]["@timestamp"]["lte"] = req.to_time
            query_body["query"]["bool"]["filter"].append(range_filter)

        # Pagination (from/size)
        if req.page_token:
            try:
                query_body["from"] = int(req.page_token)
            except ValueError:
                pass

        try:
            # Call 'search' tool
            result = await self._call("search", {"index": index, "query_body": query_body})
            
            # Parse Hits
            # ES response structure: {"hits": {"hits": [...]}}
            hits = result.get("hits", {}).get("hits", [])
            total_val = result.get("hits", {}).get("total", {}).get("value", 0)

            datasets = []
            for hit in hits:
                doc_id = hit.get("_id")
                source = hit.get("_source", {})
                
                # Create a composite ID so datasets_get knows the index
                # Format: "index_name::doc_id"
                composite_id = f"{index}::{doc_id}"
                
                datasets.append(
                    DatasetInfo(
                        dataset_id=composite_id,
                        run_id="unknown", # No run concept
                        test_id=index,
                        name=f"Log {doc_id}",
                        created_at=source.get("@timestamp"), # Best effort
                        content_type="application/json"
                    )
                )

            # Calculate pagination
            current_from = query_body.get("from", 0)
            next_from = current_from + len(hits)
            has_more = next_from < total_val
            
            return DatasetsSearchResponse(
                datasets=datasets,
                pagination=Pagination(
                    has_more=has_more,
                    next_page_token=str(next_from) if has_more else None,
                    total_count=total_val
                )
            )

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return DatasetsSearchResponse(
                datasets=[], 
                pagination=Pagination(has_more=False)
            )

    async def datasets_get(self, req: DatasetsGetRequest) -> DatasetsGetResponse:
        """Fetch a single document by ID."""
        
        # Parse composite ID "index::doc_id"
        if "::" not in req.dataset_id:
             raise ValueError("Invalid dataset_id format. Expected 'index::doc_id'")
        
        index, doc_id = req.dataset_id.split("::", 1)

        # We can use a 'get_document' tool if available, or 'search' by ID.
        # Assuming 'search' is the safe bet for the template.
        query_body = {
            "query": {
                "ids": {
                    "values": [doc_id]
                }
            }
        }
        
        result = await self._call("search", {"index": index, "query_body": query_body})
        hits = result.get("hits", {}).get("hits", [])
        
        if not hits:
             raise ValueError(f"Document not found: {req.dataset_id}")
             
        doc = hits[0]
        content = doc.get("_source", {})
        
        # Inject metadata if useful
        content["_es_id"] = doc.get("_id")
        content["_es_index"] = doc.get("_index")

        return DatasetsGetResponse(
            dataset_id=req.dataset_id,
            content=content,
            content_type="application/json"
        )

    # Label values are not natively supported by standard ES, 
    # but could be implemented as Aggregations in the future.
    # For now, return empty to force "Dataset" path.
    async def get_run_label_values(self, req: RunLabelValuesRequest) -> RunLabelValuesResponse:
        return RunLabelValuesResponse(items=[], pagination=Pagination(has_more=False))

    async def get_test_label_values(self, req: TestLabelValuesRequest) -> TestLabelValuesResponse:
        return TestLabelValuesResponse(items=[], pagination=Pagination(has_more=False))

    async def get_dataset_label_values(self, req: DatasetLabelValuesRequest) -> DatasetLabelValuesResponse:
        return DatasetLabelValuesResponse(values=[])

    async def artifacts_get(self, req: ArtifactsGetRequest) -> ArtifactsGetResponse:
        raise NotImplementedError("Artifacts not supported by Elasticsearch adapter")
