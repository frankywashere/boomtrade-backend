#!/usr/bin/env python3
"""
Direct IBeam runner that imports and starts IBeam
"""
import os
import sys
import time
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get credentials from environment
account = os.getenv('IBEAM_ACCOUNT', '')
password = os.getenv('IBEAM_PASSWORD', '')

logger.info("=== IBEAM STARTUP ===")
logger.info(f"Account configured: {'Yes' if account else 'No'}")
logger.info(f"Password configured: {'Yes' if password else 'No'}")

# If no credentials, just exit gracefully
if not account or not password:
    logger.warning("No IBKR credentials configured. IBeam will not start.")
    logger.warning("Set IBEAM_ACCOUNT and IBEAM_PASSWORD environment variables in Render.")
    # Exit with 0 to prevent supervisor from retrying
    sys.exit(0)

try:
    from ibeam import IBeam
    logger.info("✅ IBeam module imported successfully")
    
    # Initialize IBeam
    logger.info("Initializing IBeam...")
    ib = IBeam(
        account=account,
        password=password,
        gateway_dir='/tmp/gateway',
        cache_dir='/tmp/cache'
    )
    
    logger.info("Starting IBeam authentication...")
    
    # Start and authenticate
    success = ib.start_and_authenticate()
    
    if success:
        logger.info("✅ IBeam authentication successful!")
        # Keep running
        while True:
            time.sleep(30)
            logger.debug("IBeam heartbeat...")
    else:
        logger.error("❌ IBeam authentication failed")
        sys.exit(0)
        
except ImportError as e:
    logger.error(f"❌ Failed to import IBeam: {e}")
    logger.info("IBeam not properly installed. Running without IBeam.")
    sys.exit(0)
    
except Exception as e:
    logger.error(f"❌ Error starting IBeam: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(0)