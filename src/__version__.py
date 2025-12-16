"""
Version information for RHIVOS PerfScale MCP.

This module provides centralized version tracking for the project.
Version numbers follow semantic versioning (https://semver.org/).

The package version is read from pyproject.toml via importlib.metadata.
This ensures a single source of truth for version management.
"""

try:
    from importlib.metadata import version

    __version__ = version("domain-mcp-server")
except Exception:
    # Fallback for development (package not installed)
    # Read directly from pyproject.toml
    import tomllib
    from pathlib import Path

    try:
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
            __version__ = pyproject["project"]["version"]
    except Exception:
        # Last resort fallback
        __version__ = "0.0.0-dev"

# Domain model version for API responses (separate from package version)
__domain_model_version__ = "1.0.0"
