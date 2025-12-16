#!/usr/bin/env python3
"""
Connection Verification Script

This script verifies that your Domain MCP can connect to the configured Source MCP.
Run this after Phase 1 (project initialization) to ensure your adapter configuration is correct.

Usage:
    python scripts/verify_connection.py

Expected output:
    - Connection successful: Prints Source MCP info (name, version, capabilities)
    - Connection failed: Prints error details for troubleshooting

Environment:
    Configure your adapter settings in config.json or environment variables before running.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.models import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def verify_connection() -> bool:
    """
    Verify connection to Source MCP by calling source_describe().
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        logger.info("🔍 Loading configuration...")
        config = Config.load()
        logger.info(f"✓ Configuration loaded: {config.adapter_type} adapter")
        
        logger.info("🔌 Initializing adapter...")
        
        # Import the appropriate adapter based on config
        if config.adapter_type == "elasticsearch":
            from src.adapters.elasticsearch import ElasticsearchAdapter as Adapter
        elif config.adapter_type == "horreum":
            from src.adapters.horreum import HorreumAdapter as Adapter
        else:
            logger.error(f"❌ Unknown adapter type: {config.adapter_type}")
            logger.info("Valid adapter types: elasticsearch, horreum")
            return False
        
        # Create adapter instance
        adapter = Adapter(config)
        logger.info(f"✓ {config.adapter_type.title()} adapter initialized")
        
        logger.info("📡 Connecting to Source MCP...")
        logger.info(f"   Command: {config.elasticsearch_mcp_command if config.adapter_type == 'elasticsearch' else config.horreum_mcp_url}")
        
        # Call source_describe() to verify connection
        result = await adapter.source_describe()
        
        logger.info("✅ CONNECTION SUCCESSFUL!")
        logger.info("")
        logger.info("Source MCP Information:")
        logger.info(f"  Name: {result.get('name', 'Unknown')}")
        logger.info(f"  Version: {result.get('version', 'Unknown')}")
        
        if 'capabilities' in result:
            capabilities = result['capabilities']
            logger.info(f"  Capabilities:")
            for capability, supported in capabilities.items():
                status = "✓" if supported else "✗"
                logger.info(f"    {status} {capability}")
        
        if 'metadata' in result:
            logger.info(f"  Metadata: {json.dumps(result['metadata'], indent=4)}")
        
        logger.info("")
        logger.info("🎉 Your adapter configuration is working correctly!")
        logger.info("   You can now proceed to Phase 3 (Domain Implementation)")
        
        return True
        
    except FileNotFoundError as e:
        logger.error("❌ Configuration file not found")
        logger.error(f"   Error: {e}")
        logger.info("")
        logger.info("💡 Troubleshooting:")
        logger.info("   1. Ensure config.json exists in the project root")
        logger.info("   2. Or set environment variables (see README.md)")
        return False
        
    except ImportError as e:
        logger.error("❌ Could not import adapter module")
        logger.error(f"   Error: {e}")
        logger.info("")
        logger.info("💡 Troubleshooting:")
        logger.info("   1. Check that dependencies are installed: pip install -r requirements.txt")
        logger.info("   2. Verify the adapter file exists in src/adapters/")
        return False
        
    except ConnectionError as e:
        logger.error("❌ Failed to connect to Source MCP")
        logger.error(f"   Error: {e}")
        logger.info("")
        logger.info("💡 Troubleshooting:")
        logger.info("   1. Verify Source MCP is running")
        logger.info("   2. Check connection URL/command in config.json")
        logger.info("   3. Test Source MCP separately (e.g., curl for HTTP endpoints)")
        return False
        
    except Exception as e:
        logger.error("❌ Unexpected error during connection verification")
        logger.error(f"   Error: {e}", exc_info=True)
        logger.info("")
        logger.info("💡 Troubleshooting:")
        logger.info("   1. Check logs above for details")
        logger.info("   2. Verify config.json format is correct")
        logger.info("   3. Ensure Source MCP is accessible")
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

