"""
Pagination edge case testing for dataset fetching.

Tests boundary conditions, empty results, single pages, and error scenarios
to ensure robust pagination behavior.
"""

from unittest.mock import AsyncMock

import pytest

from src.schemas.source_mcp_contract import (
    DatasetInfo,
    DatasetsGetResponse,
    DatasetsSearchResponse,
    Pagination,
)
from src.server.http import _fetch_source_datasets
from src.server.models import GetKeyMetricsRequest


@pytest.mark.asyncio
async def test_pagination_empty_results():
    """Test pagination when no datasets are found."""
    mock_adapter = AsyncMock()
    mock_adapter.datasets_search.return_value = DatasetsSearchResponse(
        datasets=[],
        pagination=Pagination(
            has_more=False,
            next_page_token=None,
            total_count=0,
        ),
    )

    req = GetKeyMetricsRequest(test_id="262", limit=100)
    results = await _fetch_source_datasets(mock_adapter, req)

    assert results == []
    assert mock_adapter.datasets_search.call_count == 1
    assert mock_adapter.datasets_get.call_count == 0


@pytest.mark.asyncio
async def test_pagination_single_page():
    """Test pagination with all results fitting in a single page."""
    mock_adapter = AsyncMock()

    # Mock datasets_search to return 3 datasets, no more pages
    mock_adapter.datasets_search.return_value = DatasetsSearchResponse(
        datasets=[
            DatasetInfo(
                dataset_id="101", run_id="1001", test_id="262", schema_uri="urn:test:01"
            ),
            DatasetInfo(
                dataset_id="102", run_id="1002", test_id="262", schema_uri="urn:test:01"
            ),
            DatasetInfo(
                dataset_id="103", run_id="1003", test_id="262", schema_uri="urn:test:01"
            ),
        ],
        pagination=Pagination(
            has_more=False,
            next_page_token=None,
            total_count=3,
        ),
    )

    # Mock datasets_get to return content
    def get_dataset(request):
        return DatasetsGetResponse(
            dataset_id=request.dataset_id,
            content={"id": request.dataset_id, "data": "test_data"},
        )

    mock_adapter.datasets_get.side_effect = get_dataset

    req = GetKeyMetricsRequest(test_id="262", limit=100)
    results = await _fetch_source_datasets(mock_adapter, req)

    assert len(results) == 3
    assert mock_adapter.datasets_search.call_count == 1
    assert mock_adapter.datasets_get.call_count == 3
    assert results[0]["id"] == "101"
    assert results[1]["id"] == "102"
    assert results[2]["id"] == "103"


@pytest.mark.asyncio
async def test_pagination_multiple_pages():
    """Test pagination across multiple pages."""
    mock_adapter = AsyncMock()

    # Page 1: 2 datasets, more available
    page1_response = DatasetsSearchResponse(
        datasets=[
            DatasetInfo(
                dataset_id="201", run_id="2001", test_id="262", schema_uri="urn:test:01"
            ),
            DatasetInfo(
                dataset_id="202", run_id="2002", test_id="262", schema_uri="urn:test:01"
            ),
        ],
        pagination=Pagination(
            has_more=True,
            next_page_token="page2_token",
            total_count=5,
        ),
    )

    # Page 2: 2 datasets, more available
    page2_response = DatasetsSearchResponse(
        datasets=[
            DatasetInfo(
                dataset_id="203", run_id="2003", test_id="262", schema_uri="urn:test:01"
            ),
            DatasetInfo(
                dataset_id="204", run_id="2004", test_id="262", schema_uri="urn:test:01"
            ),
        ],
        pagination=Pagination(
            has_more=True,
            next_page_token="page3_token",
            total_count=5,
        ),
    )

    # Page 3: 1 dataset, no more
    page3_response = DatasetsSearchResponse(
        datasets=[
            DatasetInfo(
                dataset_id="205", run_id="2005", test_id="262", schema_uri="urn:test:01"
            ),
        ],
        pagination=Pagination(
            has_more=False,
            next_page_token=None,
            total_count=5,
        ),
    )

    mock_adapter.datasets_search.side_effect = [
        page1_response,
        page2_response,
        page3_response,
    ]

    def get_dataset(request):
        return DatasetsGetResponse(
            dataset_id=request.dataset_id,
            content={"id": request.dataset_id, "data": f"data_{request.dataset_id}"},
        )

    mock_adapter.datasets_get.side_effect = get_dataset

    req = GetKeyMetricsRequest(test_id="262", limit=2)
    results = await _fetch_source_datasets(mock_adapter, req)

    assert len(results) == 5
    assert mock_adapter.datasets_search.call_count == 3
    assert mock_adapter.datasets_get.call_count == 5
    # Verify all datasets were fetched in order
    for i, result in enumerate(results, start=1):
        assert result["id"] == f"20{i}"


@pytest.mark.asyncio
async def test_pagination_has_more_but_no_token():
    """Test pagination safety when has_more=True but no next_page_token."""
    mock_adapter = AsyncMock()

    # Malformed pagination: has_more=True but no token (should break loop)
    mock_adapter.datasets_search.return_value = DatasetsSearchResponse(
        datasets=[
            DatasetInfo(
                dataset_id="301", run_id="3001", test_id="262", schema_uri="urn:test:01"
            ),
        ],
        pagination=Pagination(
            has_more=True,
            next_page_token=None,  # Missing token!
            total_count=10,
        ),
    )

    mock_adapter.datasets_get.return_value = DatasetsGetResponse(
        dataset_id="301",
        content={"id": "301", "data": "test_data"},
    )

    req = GetKeyMetricsRequest(test_id="262", limit=100)
    results = await _fetch_source_datasets(mock_adapter, req)

    # Should fetch what's available and break (not infinite loop)
    assert len(results) == 1
    assert mock_adapter.datasets_search.call_count == 1  # Only called once
    assert mock_adapter.datasets_get.call_count == 1


@pytest.mark.asyncio
async def test_pagination_dataset_content_as_list():
    """Test handling when dataset content is returned as a list."""
    mock_adapter = AsyncMock()

    mock_adapter.datasets_search.return_value = DatasetsSearchResponse(
        datasets=[
            DatasetInfo(
                dataset_id="401", run_id="4001", test_id="262", schema_uri="urn:test:01"
            ),
        ],
        pagination=Pagination(
            has_more=False,
            next_page_token=None,
            total_count=1,
        ),
    )

    # Horreum sometimes returns content as a list
    mock_adapter.datasets_get.return_value = DatasetsGetResponse(
        dataset_id="401",
        content=[
            {"id": "401a", "data": "first_item"},
            {"id": "401b", "data": "second_item"},
        ],
    )

    req = GetKeyMetricsRequest(test_id="262", limit=100)
    results = await _fetch_source_datasets(mock_adapter, req)

    # Should extract both items from the list
    assert len(results) == 2
    assert results[0]["id"] == "401a"
    assert results[1]["id"] == "401b"


@pytest.mark.asyncio
async def test_pagination_boundary_page_size_one():
    """Test pagination with page_size=1 (boundary condition)."""
    mock_adapter = AsyncMock()

    # 3 pages, 1 dataset each
    responses = [
        DatasetsSearchResponse(
            datasets=[
                DatasetInfo(
                    dataset_id=f"50{i}",
                    run_id=f"500{i}",
                    test_id="262",
                    schema_uri="urn:test:01",
                )
            ],
            pagination=Pagination(
                has_more=(i < 3),
                next_page_token=f"page{i+1}_token" if i < 3 else None,
                total_count=3,
            ),
        )
        for i in range(1, 4)
    ]

    mock_adapter.datasets_search.side_effect = responses

    def get_dataset(request):
        return DatasetsGetResponse(
            dataset_id=request.dataset_id,
            content={"id": request.dataset_id, "data": "test"},
        )

    mock_adapter.datasets_get.side_effect = get_dataset

    req = GetKeyMetricsRequest(test_id="262", limit=1)
    results = await _fetch_source_datasets(mock_adapter, req)

    assert len(results) == 3
    assert mock_adapter.datasets_search.call_count == 3
    assert mock_adapter.datasets_get.call_count == 3


@pytest.mark.asyncio
async def test_pagination_with_time_filters():
    """Test pagination with from/to timestamp filters."""
    mock_adapter = AsyncMock()

    mock_adapter.datasets_search.return_value = DatasetsSearchResponse(
        datasets=[
            DatasetInfo(
                dataset_id="601", run_id="6001", test_id="262", schema_uri="urn:test:01"
            ),
        ],
        pagination=Pagination(
            has_more=False,
            next_page_token=None,
            total_count=1,
        ),
    )

    mock_adapter.datasets_get.return_value = DatasetsGetResponse(
        dataset_id="601",
        content={"id": "601", "timestamp": "2025-10-15T00:00:00Z"},
    )

    req = GetKeyMetricsRequest(
        test_id="262",
        from_timestamp="2025-10-01",
        to_timestamp="2025-10-15",
        limit=100,
    )
    results = await _fetch_source_datasets(mock_adapter, req)

    assert len(results) == 1
    # Verify time filters were passed to datasets_search
    call_args = mock_adapter.datasets_search.call_args[0][0]
    assert call_args.from_time == "2025-10-01"
    assert call_args.to_time == "2025-10-15"


@pytest.mark.asyncio
async def test_pagination_preserves_page_token():
    """Test that page tokens are correctly passed between pages."""
    mock_adapter = AsyncMock()

    page1_response = DatasetsSearchResponse(
        datasets=[
            DatasetInfo(
                dataset_id="701", run_id="7001", test_id="262", schema_uri="urn:test:01"
            ),
        ],
        pagination=Pagination(
            has_more=True,
            next_page_token="abc123token",
            total_count=2,
        ),
    )

    page2_response = DatasetsSearchResponse(
        datasets=[
            DatasetInfo(
                dataset_id="702", run_id="7002", test_id="262", schema_uri="urn:test:01"
            ),
        ],
        pagination=Pagination(
            has_more=False,
            next_page_token=None,
            total_count=2,
        ),
    )

    mock_adapter.datasets_search.side_effect = [page1_response, page2_response]

    def get_dataset(request):
        return DatasetsGetResponse(
            dataset_id=request.dataset_id,
            content={"id": request.dataset_id},
        )

    mock_adapter.datasets_get.side_effect = get_dataset

    req = GetKeyMetricsRequest(test_id="262", limit=1)
    results = await _fetch_source_datasets(mock_adapter, req)

    assert len(results) == 2
    # Verify second call included page_token
    second_call_args = mock_adapter.datasets_search.call_args_list[1][0][0]
    assert second_call_args.page_token == "abc123token"


@pytest.mark.asyncio
async def test_pagination_large_page_size():
    """Test pagination with very large page_size (boundary condition)."""
    mock_adapter = AsyncMock()

    # Even with large page size, should handle normally
    mock_adapter.datasets_search.return_value = DatasetsSearchResponse(
        datasets=[
            DatasetInfo(
                dataset_id=f"80{i}",
                run_id=f"800{i}",
                test_id="262",
                schema_uri="urn:test:01",
            )
            for i in range(1, 6)
        ],
        pagination=Pagination(
            has_more=False,
            next_page_token=None,
            total_count=5,
        ),
    )

    def get_dataset(request):
        return DatasetsGetResponse(
            dataset_id=request.dataset_id,
            content={"id": request.dataset_id},
        )

    mock_adapter.datasets_get.side_effect = get_dataset

    req = GetKeyMetricsRequest(test_id="262", limit=1000)  # Max allowed is 1000
    results = await _fetch_source_datasets(mock_adapter, req)

    assert len(results) == 5
    assert mock_adapter.datasets_search.call_count == 1


@pytest.mark.asyncio
async def test_pagination_schema_uri_filter():
    """Test pagination with schema_uri filter."""
    mock_adapter = AsyncMock()

    mock_adapter.datasets_search.return_value = DatasetsSearchResponse(
        datasets=[
            DatasetInfo(
                dataset_id="901",
                run_id="9001",
                test_id="262",
                schema_uri="urn:boot-time:06",
            ),
        ],
        pagination=Pagination(
            has_more=False,
            next_page_token=None,
            total_count=1,
        ),
    )

    mock_adapter.datasets_get.return_value = DatasetsGetResponse(
        dataset_id="901",
        content={"id": "901", "schema": "urn:boot-time:06"},
    )

    req = GetKeyMetricsRequest(test_id="262", schema_uri="urn:boot-time:06", limit=100)
    results = await _fetch_source_datasets(mock_adapter, req)

    assert len(results) == 1
    # Verify schema_uri was passed
    call_args = mock_adapter.datasets_search.call_args[0][0]
    assert call_args.schema_uri == "urn:boot-time:06"


@pytest.mark.asyncio
async def test_pagination_mixed_content_types():
    """Test pagination when some datasets return dict, others return list."""
    mock_adapter = AsyncMock()

    mock_adapter.datasets_search.return_value = DatasetsSearchResponse(
        datasets=[
            DatasetInfo(
                dataset_id="1001",
                run_id="10001",
                test_id="262",
                schema_uri="urn:test:01",
            ),
            DatasetInfo(
                dataset_id="1002",
                run_id="10002",
                test_id="262",
                schema_uri="urn:test:01",
            ),
        ],
        pagination=Pagination(
            has_more=False,
            next_page_token=None,
            total_count=2,
        ),
    )

    # First returns dict, second returns list
    def get_dataset(request):
        if request.dataset_id == "1001":
            return DatasetsGetResponse(
                dataset_id="1001",
                content={"id": "1001", "type": "dict"},
            )
        else:
            return DatasetsGetResponse(
                dataset_id="1002",
                content=[
                    {"id": "1002a", "type": "list_item1"},
                    {"id": "1002b", "type": "list_item2"},
                ],
            )

    mock_adapter.datasets_get.side_effect = get_dataset

    req = GetKeyMetricsRequest(test_id="262", limit=100)
    results = await _fetch_source_datasets(mock_adapter, req)

    # Should get 3 total: 1 dict + 2 list items
    assert len(results) == 3
    assert results[0]["id"] == "1001"
    assert results[1]["id"] == "1002a"
    assert results[2]["id"] == "1002b"
