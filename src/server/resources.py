"""
MCP Resources implementation for domain knowledge exposure.

This module provides the MCP Resources protocol implementation, allowing AI
clients to fetch structured domain knowledge as JSON resources via URI patterns.

Resources are organized as:
- domain://glossary/* - Domain knowledge (boot-time, os-identifiers, etc.)
- domain://examples/* - Query examples and patterns
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Resource:
    """
    Represents an MCP resource with metadata and content.

    Attributes:
        uri: Unique resource identifier (e.g., domain://glossary/boot-time)
        name: Human-readable resource name
        description: Brief description of resource contents
        mime_type: Content type (application/json)
        content: Parsed JSON content
    """

    def __init__(
        self,
        uri: str,
        name: str,
        description: str,
        mime_type: str,
        content: Dict[str, Any],
    ):
        self.uri = uri
        self.name = name
        self.description = description
        self.mime_type = mime_type
        self.content = content

    def to_dict(self) -> Dict[str, Any]:
        """Convert resource to MCP resource list format (metadata only)."""
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }

    def read(self) -> Dict[str, Any]:
        """Read resource content in MCP format."""
        return {
            "contents": [
                {
                    "uri": self.uri,
                    "mimeType": self.mime_type,
                    "text": json.dumps(self.content, indent=2),
                }
            ]
        }


class ResourceRegistry:
    """
    Registry for MCP resources loaded from JSON files.

    Scans the src/resources directory on initialization and provides
    methods to list and read resources by URI.
    """

    def __init__(self, resources_dir: Optional[Path] = None):
        """
        Initialize resource registry.

        Args:
            resources_dir: Root directory for resources
                (default: src/resources)
        """
        if resources_dir is None:
            # Default to src/resources relative to this file
            resources_dir = Path(__file__).parent.parent / "resources"

        self.resources_dir = resources_dir
        self.resources: Dict[str, Resource] = {}
        self._load_resources()

    def _load_resources(self) -> None:
        """Load all JSON resources from resources directory."""
        if not self.resources_dir.exists():
            logger.warning(f"Resources directory not found: {self.resources_dir}")
            return

        # Load glossary resources
        glossary_dir = self.resources_dir / "glossary"
        if glossary_dir.exists():
            for json_file in glossary_dir.glob("*.json"):
                self._load_resource(
                    json_file,
                    uri_prefix="domain://glossary/",
                    category="Domain Glossary",
                )

        # Load example resources
        examples_dir = self.resources_dir / "examples"
        if examples_dir.exists():
            for json_file in examples_dir.glob("*.json"):
                self._load_resource(
                    json_file,
                    uri_prefix="domain://examples/",
                    category="Query Examples",
                )

        logger.info(f"Loaded {len(self.resources)} MCP resources")

    def _load_resource(self, json_file: Path, uri_prefix: str, category: str) -> None:
        """
        Load a single JSON resource file.

        Args:
            json_file: Path to JSON file
            uri_prefix: URI prefix (e.g., domain://glossary/)
            category: Resource category for naming
        """
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                content = json.load(f)

            # Generate URI from filename (remove .json extension)
            resource_name = json_file.stem
            uri = f"{uri_prefix}{resource_name}"

            # Extract description from content or use default
            description = content.get(
                "description",
                f"{category}: {resource_name.replace('-', ' ').title()}",
            )

            # Extract display name from content or use default
            display_name = content.get(
                "name",
                f"{resource_name.replace('-', ' ').title()}",
            )

            resource = Resource(
                uri=uri,
                name=display_name,
                description=description,
                mime_type="application/json",
                content=content,
            )

            self.resources[uri] = resource
            logger.debug(f"Loaded resource: {uri}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON in {json_file}: {e}")
        except Exception as e:
            logger.error(f"Failed to load resource {json_file}: {e}")

    def list_resources(self) -> List[Dict[str, Any]]:
        """
        List all available resources (MCP resources/list format).

        Returns:
            List of resource metadata dicts
        """
        return [resource.to_dict() for resource in self.resources.values()]

    def read_resource(self, uri: str) -> Optional[Dict[str, Any]]:
        """
        Read a specific resource by URI (MCP resources/read format).

        Args:
            uri: Resource URI (e.g., domain://glossary/boot-time)

        Returns:
            Resource content in MCP format, or None if not found
        """
        resource = self.resources.get(uri)
        if resource is None:
            logger.warning(f"Resource not found: {uri}")
            return None

        return resource.read()

    def get_resource_content(self, uri: str) -> Optional[Dict[str, Any]]:
        """
        Get raw resource content (for internal use).

        Args:
            uri: Resource URI

        Returns:
            Parsed JSON content, or None if not found
        """
        resource = self.resources.get(uri)
        return resource.content if resource else None


# Global registry instance (initialized on module import)
_registry: Optional[ResourceRegistry] = None


def get_registry() -> ResourceRegistry:
    """
    Get global resource registry instance.

    Creates registry on first call, returns cached instance thereafter.

    Returns:
        Global ResourceRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = ResourceRegistry()
    return _registry


def list_resources() -> List[Dict[str, Any]]:
    """
    List all available MCP resources.

    Returns:
        List of resource metadata dicts
    """
    return get_registry().list_resources()


def read_resource(uri: str) -> Optional[Dict[str, Any]]:
    """
    Read a specific MCP resource by URI.

    Args:
        uri: Resource URI (e.g., domain://glossary/boot-time)

    Returns:
        Resource content in MCP format, or None if not found
    """
    return get_registry().read_resource(uri)
