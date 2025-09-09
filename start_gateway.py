#!/usr/bin/env python3
"""
Proper way to start IBeam based on the documentation
"""
import os
import sys
import time
import subprocess

# Set environment variables
os.environ['IBEAM_ACCOUNT'] = os.getenv('IBEAM_ACCOUNT', '')
os.environ['IBEAM_PASSWORD'] = os.getenv('IBEAM_PASSWORD', '')

print("Starting IBeam Gateway...")

# Find ibeam_starter.py
possible_paths = [
    "/usr/local/lib/python3.11/site-packages/ibeam/ibeam_starter.py",
    "/usr/local/lib/python3.11/site-packages/ibeam/src/ibeam_starter.py",
    "/srv/ibeam/ibeam_starter.py",
]

starter_path = None
for path in possible_paths:
    if os.path.exists(path):
        starter_path = path
        print(f"Found ibeam_starter.py at: {path}")
        break

if not starter_path:
    # Try to find it
    result = subprocess.run(
        "find / -name 'ibeam_starter.py' 2>/dev/null | head -1",
        shell=True,
        capture_output=True,
        text=True
    )
    if result.stdout.strip():
        starter_path = result.stdout.strip()
        print(f"Found ibeam_starter.py at: {starter_path}")

if starter_path:
    print(f"Starting IBeam with: python3 {starter_path}")
    subprocess.run([sys.executable, starter_path])
else:
    print("ERROR: Could not find ibeam_starter.py")
    print("\nSearching for IBeam files...")
    subprocess.run("ls -la /usr/local/lib/python3.11/site-packages/ibeam/", shell=True)
    sys.exit(1)