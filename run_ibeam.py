#!/usr/bin/env python3
"""
Direct IBeam runner that imports and starts IBeam
"""
import os
import sys
import time

# Set environment from Docker env vars
os.environ['IBEAM_ACCOUNT'] = os.getenv('IBEAM_ACCOUNT', '')
os.environ['IBEAM_PASSWORD'] = os.getenv('IBEAM_PASSWORD', '')

print("=== STARTING IBEAM DIRECTLY ===")
print(f"Account: {os.environ.get('IBEAM_ACCOUNT', 'Not set')}")

try:
    from ibeam import IBeam
    
    print("✅ IBeam module imported successfully")
    
    # Initialize IBeam
    ib = IBeam(
        account=os.environ.get('IBEAM_ACCOUNT'),
        password=os.environ.get('IBEAM_PASSWORD'),
        gateway_dir='/tmp/gateway',
        cache_dir='/tmp/cache'
    )
    
    print("Starting IBeam authentication...")
    
    # Start and authenticate
    ib.start_and_authenticate()
    
    print("✅ IBeam is running!")
    
    # Keep running
    while True:
        time.sleep(10)
        
except ImportError as e:
    print(f"❌ Failed to import IBeam: {e}")
    print("Trying alternative approach...")
    
    # Try to run IBeam CLI directly
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "ibeam", "gateway", "start"],
        env=os.environ.copy()
    )
    
except Exception as e:
    print(f"❌ Error starting IBeam: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)