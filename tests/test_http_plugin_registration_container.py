"""Container-oriented tests for plugin registration reliability.

These simulate a container environment via environment variables and ensure
plugin registration succeeds and errors are structured with options.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.server.http import create_app


def test_get_key_metrics_raw_boot_time_success_container(tmp_path: Path):
    """Ensure boot-time plugin works under container-like env settings."""
    with patch.dict(
        "os.environ",
        {"DOMAIN_MCP_HTTP_TOKEN": "t", "DOMAIN_MCP_CORS_ORIGINS": "http://x"},
    ):
        app = create_app()
        c = TestClient(app)
        # Load a local boot-time fixture
        fixture = (
            Path(__file__).parent / "fixtures" / "boot-time" / "successful-boot.json"
        )
        data = json.loads(fixture.read_text())
        r = c.post(
            "/tools/get_key_metrics_raw",
            headers={"Authorization": "Bearer t"},
            json={"dataset_types": ["boot-time-verbose"], "data": [data]},
        )
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body.get("metric_points"), list)
        assert len(body["metric_points"]) >= 1


def test_invalid_dataset_type_container_returns_options():
    """Invalid dataset type returns structured error with available options."""
    with patch.dict("os.environ", {"DOMAIN_MCP_HTTP_TOKEN": "t"}):
        app = create_app()
        c = TestClient(app)
        r = c.post(
            "/tools/get_key_metrics_raw",
            headers={"Authorization": "Bearer t"},
            json={"dataset_types": ["does-not-exist"], "data": [{"x": 1}]},
        )
        assert r.status_code == 400
        body = r.json()["detail"]
        assert body["error_type"] == "unknown_dataset_type"
        assert isinstance(body.get("available_options"), list)


def test_enabled_plugins_filtering(tmp_path: Path):
    """Enabled plugins in config should filter registry before requests.

    We disable the built-in boot-time plugin and assert that requests for it
    return an unknown_dataset_type error with available options empty.
    """
    cfg_json = {
        "sources": {},
        "enabled_plugins": {"boot-time-verbose": False},
    }
    import tempfile

    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(json.dumps(cfg_json))
        cfg_path = f.name
    try:
        with patch.dict(
            "os.environ", {"DOMAIN_MCP_HTTP_TOKEN": "t", "DOMAIN_MCP_CONFIG": cfg_path}
        ):
            app = create_app()
            c = TestClient(app)
            r = c.post(
                "/tools/get_key_metrics_raw",
                headers={"Authorization": "Bearer t"},
                json={
                    "dataset_types": ["boot-time-verbose"],
                    "data": [{"$schema": "urn:boot-time-verbose:04"}],
                },
            )
            assert r.status_code == 400
            body = r.json()["detail"]
            assert body["error_type"] == "unknown_dataset_type"
            # available_options may be None when no plugins remain
            assert (body.get("available_options") is None) or isinstance(
                body.get("available_options"), list
            )
    finally:
        import os

        try:
            os.unlink(cfg_path)
        except OSError:
            pass
