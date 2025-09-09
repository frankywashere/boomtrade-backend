#!/usr/bin/env python3
"""
IBeam service that waits for credentials from the API
"""
import os
import sys
import time
import logging
import json
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info("=== IBEAM SERVICE STARTED ===")
logger.info("Waiting for user credentials from API...")

# Just keep the service running - it will be managed by the API
while True:
    time.sleep(60)
    logger.debug("IBeam service idle - waiting for API to start gateway...")