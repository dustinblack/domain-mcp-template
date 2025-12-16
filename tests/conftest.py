"""Pytest configuration for test suite.

Ensures the project root is on ``sys.path`` so imports like ``import src``
resolve correctly regardless of the working directory pytest chooses.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _ensure_project_root_on_syspath() -> None:
    project_root = Path(__file__).resolve().parents[1]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        # Prepend to prefer local sources over site-packages
        sys.path.insert(0, project_root_str)


_ensure_project_root_on_syspath()


@pytest.fixture(autouse=True)
def reset_plugin_registry():
    """Reset plugin registry before each test to avoid cross-test contamination.

    This ensures each test starts with a clean, default plugin state.
    """
    from src.domain.plugins import reset_plugins

    reset_plugins()
    yield
    # Cleanup after test if needed
