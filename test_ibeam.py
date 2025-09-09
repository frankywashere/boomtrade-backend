#!/usr/bin/env python3
"""
Simple test to verify IBeam can start
"""
import os
import subprocess
import time

print("=== IBEAM START TEST ===")

# Try to find IBeam
commands = [
    "which ibeam",
    "pip show ibeam",
    "python3 -c 'import ibeam; print(ibeam.__file__)'",
]

for cmd in commands:
    print(f"\nTrying: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(f"Output: {result.stdout}")
    if result.stderr:
        print(f"Error: {result.stderr}")

# Try to start IBeam directly
print("\n=== Attempting to start IBeam ===")
try:
    # Set minimal environment
    os.environ['IBEAM_ACCOUNT'] = 'test'
    os.environ['IBEAM_PASSWORD'] = 'test'
    
    # Try importing IBeam
    try:
        import ibeam
        print(f"✅ IBeam module found at: {ibeam.__file__}")
    except ImportError as e:
        print(f"❌ Cannot import IBeam: {e}")
        
    # Try running IBeam CLI
    result = subprocess.run(
        "python3 -m ibeam --help",
        shell=True,
        capture_output=True,
        text=True,
        timeout=5
    )
    if result.returncode == 0:
        print("✅ IBeam CLI works!")
    else:
        print(f"❌ IBeam CLI failed: {result.stderr}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n=== TEST COMPLETE ===")