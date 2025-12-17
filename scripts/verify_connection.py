#!/usr/bin/env python3
"""
Connection Verification Script

This script verifies that your Domain MCP can connect to the configured Source MCPs.
Run this after Phase 1 (project initialization) to ensure your adapter
configuration is correct.

Usage:
    python scripts/verify_connection.py

Expected output:
    - Connection successful: Prints Source MCP info (name, version, capabilities)
    - Connection failed: Prints error details for troubleshooting

Environment:
    Configure your adapter settings in config.json before running.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from src.adapters import SourceAdapter
    from src.config.models import AppConfig
    from src.schemas.source_mcp_contract import SourceDescribeRequest, TestsListRequest
except ImportError as e:
    print(f"❌ Critical Import Error: {e}")
    print("   Ensure you are running from project root; dependencies installed.")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def verify_single_source(source_id: str, source_config) -> bool:
    """Verify a single source connection."""
    logger.info("-" * 50)
    logger.info(f"🔌 Verifying source: {source_id} ({source_config.type})")

    try:
        adapter: SourceAdapter | None = None
        if "elasticsearch" in source_config.type:
            from src.adapters.elasticsearch import ElasticsearchAdapter

            # Elasticsearch adapter uses stdio bridge (command + args)
            adapter = ElasticsearchAdapter(
                command=source_config.endpoint,
                args=source_config.stdio_args,
                timeout=source_config.timeout_seconds,
                env=source_config.env,
            )
        elif "horreum" in source_config.type:
            from src.adapters.horreum import HorreumAdapter

            # Horreum adapter uses HTTP (endpoint + api_key)
            adapter = HorreumAdapter(
                endpoint=source_config.endpoint,
                api_key=source_config.api_key,
                timeout=source_config.timeout_seconds,
                max_retries=source_config.max_retries,
                backoff_initial_ms=source_config.backoff_initial_ms,
                backoff_multiplier=source_config.backoff_multiplier,
            )
        else:
            logger.error(f"❌ Unknown source type: {source_config.type}")
            logger.info("   Valid types: 'elasticsearch' or 'horreum'")
            return False

        if adapter is None:
            logger.error("❌ Adapter initialization failed")
            return False

        logger.info(f"✓ {source_config.type} adapter initialized")
        logger.info("📡 Connecting to Source MCP...")
        logger.info(f"   Target: {source_config.endpoint}")

        # 1. Get Static/Describe Info
        describe_result = await adapter.source_describe(SourceDescribeRequest())

        # 2. Verify Active Connection (call tests_list)
        logger.info("   Calling tests_list() to verify active connection...")
        list_result = await adapter.tests_list(
            TestsListRequest(page_size=1, query=None, tags=None, page_token=None)
        )

        logger.info("✅ CONNECTION SUCCESSFUL!")
        logger.info("")
        logger.info("Source MCP Information:")
        logger.info(f"  Source Type: {describe_result.source_type}")
        logger.info(f"  Version: {describe_result.version}")
        logger.info(f"  Contract: {describe_result.contract_version}")

        if describe_result.capabilities:
            logger.info("  Capabilities:")
            # Dump model to dict to iterate
            caps = describe_result.capabilities.model_dump(exclude_none=True)
            for capability, supported in caps.items():
                status = "✓" if supported else "✗"
                logger.info(f"    {status} {capability}")

        logger.info("")
        logger.info("Active Connection Check:")
        total_count_str = (
            str(list_result.pagination.total_count)
            if list_result.pagination
            else "Unknown"
        )
        logger.info(f"  Tests/Indices Accessible: {total_count_str}")
        if list_result.tests:
            logger.info(f"  Sample: {list_result.tests[0].name}")

        return True

    except ImportError as e:
        logger.error(f"❌ Could not import adapter module for {source_config.type}")
        logger.error(f"   Error: {e}")
        logger.info("")
        logger.info("💡 Troubleshooting:")
        logger.info("   1. Check dependencies installed: ")
        logger.info("      pip install -r requirements.txt")
        return False

    except Exception as e:
        logger.error(f"❌ Failed to connect to Source MCP '{source_id}'")
        logger.error(f"   Error: {e}")
        logger.info("")
        logger.info("💡 Troubleshooting:")
        logger.info("   1. Verify Source MCP is running/accessible")
        logger.info("   2. Check connection URL/command in config.json")
        logger.info(f"   3. Check logs for details on '{source_id}'")
        return False


async def verify_connection() -> bool:
    """
    Verify connection to all configured Source MCPs.
    """
    config_path = Path("config.json")

    try:
        logger.info(f"🔍 Loading configuration from {config_path}...")
        if not config_path.exists():
            raise FileNotFoundError(f"{config_path} does not exist")

        config = AppConfig.load(config_path)

        if not config.sources:
            logger.warning("⚠️ No sources configured in config.json.")
            logger.info("   Add sources to 'sources' block in config.json")
            return True

        logger.info(f"✓ Configuration loaded: {len(config.sources)} source(s) found")

        results = []
        for source_id, source_config in config.sources.items():
            success = await verify_single_source(source_id, source_config)
            results.append(success)

        all_success = all(results)

        logger.info("-" * 50)
        if all_success:
            logger.info("🎉 Your adapter configuration is working correctly!")
            logger.info("   You can now proceed to Phase 3 (Domain Implementation)")
        else:
            logger.error("❌ Some adapters failed verification. See logs above.")

        return all_success

    except FileNotFoundError as e:
        logger.error("❌ Configuration file not found")
        logger.error(f"   Error: {e}")
        logger.info("")
        logger.info("💡 Troubleshooting:")
        logger.info("   1. Ensure config.json exists in the project root")
        logger.info("   2. Copy config-horreum-example.json to config.json")
        return False

    except Exception as e:
        logger.error("❌ Unexpected error during configuration loading")
        logger.error(f"   Error: {e}", exc_info=True)
        logger.info("")
        logger.info("💡 Troubleshooting:")
        logger.info("   1. Verify config.json format is correct JSON")
        logger.info("   2. Check for missing required fields in config")
        return False


def main():
    """Main entry point."""
    print("=" * 70)
    print("Domain MCP - Source Connection Verification")
    print("=" * 70)
    print()

    success = asyncio.run(verify_connection())

    print()
    print("=" * 70)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
