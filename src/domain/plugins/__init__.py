"""Dataset-type plugin registry and base API.

This module defines the minimal plugin protocol that dataset-type domain packs
must implement and provides a simple in-memory registry for discovery.

Plugins are responsible for translating raw dataset JSON into canonical
`MetricPoint` observations that the Domain MCP can aggregate and analyze.
"""

# pylint: disable=too-few-public-methods

from __future__ import annotations

import importlib.util as _ilu
import logging
import os
import sys
from importlib import import_module
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Protocol

from ..models import MetricPoint

if TYPE_CHECKING:
    from ...schemas.source_mcp_contract import ExportedLabelValues

logger = logging.getLogger(__name__)


class Plugin(Protocol):
    """Dataset-type plugin contract.

    A plugin declares:
    - `id`: unique identifier (e.g., "boot-time-verbose")
    - `glossary`: mapping from metric id to description, units, etc.
    - `kpis`: list of canonical metric ids considered primary for the dataset

    Implementations must provide an async `extract` method that converts the raw
    dataset JSON and contextual references into a list of `MetricPoint`s.
    """

    id: str
    glossary: Dict[str, Dict[str, str]]
    kpis: List[str]

    async def extract(
        self,
        json_body: object,
        refs: Dict[str, str],
        label_values: Optional[List[ExportedLabelValues]] = None,
        os_filter: Optional[str] = None,
        run_type_filter: Optional[str] = None,
    ) -> List[MetricPoint]:
        """Extract canonical metric points from a raw dataset JSON or label values.

        Parameters
        ----------
        json_body: object
            Raw dataset content as parsed JSON.
        refs: Dict[str, str]
            Contextual references (e.g., runId, datasetId); may be used for
            dimension enrichment.
        label_values: Optional[List[ExportedLabelValues]]
            Optional pre-transformed label values from the source system (Phase 2.5).
            If provided, implementations should prefer extracting from these rather
            than parsing raw JSON, for improved performance.
        os_filter: Optional[str]
            Optional OS identifier filter (e.g., "rhel", "autosd"). If provided,
            implementations should filter results to only include metrics matching
            this OS. Client-side filtering for cases where server-side filtering
            is unavailable.
        run_type_filter: Optional[str]
            Optional run type filter (e.g., "nightly", "ci", "release"). If provided,
            implementations should filter results to only include metrics from matching
            run types. Client-side filtering for cases where server-side filtering
            is unavailable.

        Returns
        -------
        List[MetricPoint]
            Extracted observations. An empty list indicates no recognized data.
        """
        raise NotImplementedError


_registry: Dict[str, Plugin] = {}


def register(plugin: Plugin) -> None:
    """Register a plugin implementation by its `id`.

    Parameters
    ----------
    plugin: Plugin
        Instance to be registered. Its `id` must be unique.
    """
    _registry[plugin.id] = plugin
    logger.info(
        "Registered plugin: '%s' (KPIs: %s)",
        plugin.id,
        ", ".join(plugin.kpis),
    )


def get(plugin_id: str) -> Plugin:
    """Retrieve a plugin by `id`.

    Raises
    ------
    KeyError
        If no plugin is registered under the given identifier.
    """
    return _registry[plugin_id]


def all_plugins() -> Iterable[Plugin]:
    """Iterate over all registered plugins.

    Returns
    -------
    Iterable[Plugin]
        A view over registered plugin instances.
    """
    return _registry.values()


def log_plugin_status() -> None:
    """Log information about registered plugins and available dataset types."""
    if not _registry:
        logger.warning(
            "No plugins registered. No dataset types available for analysis.\n"
            "  - Check import paths and container mounts for plugin modules\n"
            "  - Optionally set DOMAIN_MCP_EXTRA_PYTHONPATH to include plugin dirs"
        )
    else:
        plugin_info = []
        for plugin_id, plugin in _registry.items():
            kpi_count = len(plugin.kpis)
            plugin_info.append(f"'{plugin_id}' ({kpi_count} KPIs)")

        logger.info(
            (
                "Plugins loaded: %s\n  - Available dataset types: %s\n"
                "  - Total plugins: %d"
            ),
            ", ".join(plugin_info),
            list(_registry.keys()),
            len(_registry),
        )


def log_plugin_discovery_debug() -> None:
    """Log environment details helpful for container plugin discovery.

    Includes current working directory, a condensed sys.path, and the module
    file path for each registered plugin implementation.
    """
    cwd = os.getcwd()
    sys_paths = list(sys.path)[:10]
    modules: Dict[str, str] = {}
    module_specs: Dict[str, Dict[str, object]] = {}
    for plugin_id, plugin in _registry.items():
        mod_name = plugin.__class__.__module__
        try:
            # Prefer already-loaded module to avoid side-effectful imports
            mod = sys.modules.get(mod_name) or import_module(mod_name)
            mod_file = getattr(mod, "__file__", "<unknown>")
        except (ImportError, ModuleNotFoundError):  # pragma: no cover - defensive
            mod_file = "<import-failed>"
        modules[plugin_id] = f"{mod_name}:{mod_file}"
        # Best-effort spec discovery (helps container path debugging)
        try:
            spec = _ilu.find_spec(mod_name)
            origin = getattr(spec, "origin", None) if spec else None
            locations = (
                list(getattr(spec, "submodule_search_locations", []) or [])
                if spec
                else []
            )
            module_specs[plugin_id] = {
                "module": mod_name,
                "file": mod_file,
                "spec_found": bool(spec is not None),
                "spec_origin": origin,
                "search_locations": locations[:5],
            }
        except (
            ImportError,
            AttributeError,
            TypeError,
            ValueError,
        ):  # pragma: no cover - defensive
            module_specs[plugin_id] = {
                "module": mod_name,
                "file": mod_file,
                "spec_found": False,
            }
    logger.info(
        "plugins.discovery",
        extra={
            "cwd": cwd,
            "sys_path_head": sys_paths,
            "modules": modules,
            "module_specs": module_specs,
            "plugin_count": len(_registry),
        },
    )


def apply_enabled_plugins(enabled: Dict[str, bool]) -> Dict[str, List[str]]:
    """Apply configuration-based plugin enable/disable filtering.

    Behavior:
    - When ``enabled`` is empty, no filtering is applied (all remain registered).
    - When non-empty, only plugins with ``enabled[id] is True`` are kept.

    Returns a dict with keys ``kept``, ``disabled``, and ``untouched`` for
    diagnostics and tests.
    """
    if not enabled:
        return {"kept": sorted(list(_registry.keys())), "disabled": [], "untouched": []}
    keep_ids = {pid for pid, on in enabled.items() if on}
    disabled: List[str] = []
    for pid in list(_registry.keys()):
        if pid not in keep_ids:
            disabled.append(pid)
            _registry.pop(pid, None)
    logger.info(
        "plugins.filter",
        extra={
            "requested_enabled": sorted([k for k, v in enabled.items() if v]),
            "kept": sorted(list(_registry.keys())),
            "disabled": sorted(disabled),
        },
    )
    return {
        "kept": sorted(list(_registry.keys())),
        "disabled": sorted(disabled),
        "untouched": [],
    }


def reset_plugins() -> None:
    """Reset plugin registry to default example plugins.

    This clears the in-memory registry and registers example plugins explicitly
    without relying on import-time side effects. Useful for tests and for
    HTTP app startup/shutdown to avoid cross-test contamination.
    """
    _registry.clear()
    try:
        from ..examples.elasticsearch_logs import (  # noqa: WPS433
            ElasticsearchLogsPlugin,
        )
        from ..examples.horreum_boot_time import (  # noqa: WPS433 (local import)
            BootTimePlugin,
        )

        register(BootTimePlugin())
        register(ElasticsearchLogsPlugin())
    except Exception:  # pragma: no cover - defensive
        logger.warning("Failed to reset example plugins; registry is empty")


# Import example plugins to trigger registration (after register is defined).
# Keep import simple and explicit so tests and runtime consistently register
# the default plugins without side effects elsewhere.
# NOTE: These are example plugins provided with the template. Remove or replace
# with your own domain plugins as needed.
try:
    from ..examples import elasticsearch_logs  # noqa: F401, E402
    from ..examples import horreum_boot_time as boot_time  # noqa: F401, E402
except ImportError:
    # Allow template to work even if examples are removed
    pass
