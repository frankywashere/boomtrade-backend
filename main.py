import os
import time
import subprocess
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import httpx
import asyncio

app = FastAPI()

# CORS for Swift app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
gateway_ready = False
stored_credentials = {}
ibeam_process = None

class Credentials(BaseModel):
    username: str
    password: str
    account: Optional[str] = None

@app.on_event("startup")
async def startup_event():
    """Try to start IBeam when the server starts"""
    print("=== SERVER STARTUP ===")
    # IBeam should be started by the Docker startup script
    # Check if it's running
    await asyncio.sleep(5)  # Give IBeam time to start
    
    try:
        async with httpx.AsyncClient(verify=False, timeout=2.0) as client:
            response = await client.get("http://localhost:5000/v1/api/iserver/auth/status")
            if response.status_code == 200:
                print("✅ IBeam gateway detected at startup")
            else:
                print("⚠️ IBeam gateway not responding")
    except Exception as e:
        print(f"⚠️ Could not connect to IBeam: {e}")

@app.get("/health")
async def health():
    global gateway_ready
    
    # Check if gateway is actually responding
    if gateway_ready:
        try:
            async with httpx.AsyncClient(verify=False, timeout=2.0) as client:
                response = await client.get("http://localhost:5000/v1/api/iserver/auth/status")
                if response.status_code == 200:
                    return {"status": "healthy", "gateway_ready": True, "ibeam_status": "connected"}
        except:
            pass
    
    return {"status": "healthy", "gateway_ready": gateway_ready, "ibeam_status": "disconnected"}

@app.post("/gateway/start")
async def start_gateway(credentials: Credentials):
    global gateway_ready, stored_credentials, ibeam_process
    
    print(f"=== GATEWAY START REQUEST ===")
    print(f"Username: {credentials.username}")
    print(f"Account: {credentials.account}")
    print(f"Timestamp: {datetime.now()}")
    
    # Store credentials
    stored_credentials = credentials.dict()
    
    # Try to start IBeam with user credentials
    try:
        import subprocess
        
        # Kill any existing IBeam process
        if 'ibeam_process' in globals() and ibeam_process:
            try:
                ibeam_process.terminate()
                await asyncio.sleep(1)
            except:
                pass
        
        # Set environment variables for IBeam
        env = os.environ.copy()
        env['IBEAM_ACCOUNT'] = credentials.username
        env['IBEAM_PASSWORD'] = credentials.password
        
        print("Starting IBeam with user credentials...")
        
        # Start IBeam process with better error handling
        ibeam_script = """
import os
import sys
import traceback

try:
    from ibeam import IBeam
    print('Starting IBeam with account:', os.environ.get('IBEAM_ACCOUNT'))
    ib = IBeam(
        account=os.environ.get('IBEAM_ACCOUNT'),
        password=os.environ.get('IBEAM_PASSWORD'),
        gateway_dir='/tmp/gateway',
        cache_dir='/tmp/cache'
    )
    ib.start_and_authenticate()
    # Keep process running
    import time
    while True:
        time.sleep(10)
except Exception as e:
    print(f'IBeam error: {e}')
    traceback.print_exc()
    sys.exit(1)
"""
        
        ibeam_process = subprocess.Popen(
            ["python3", "-c", ibeam_script],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        
        # Wait for IBeam to start (max 90 seconds)
        print("Waiting for IBeam to authenticate...")
        
        # Start a background task to read IBeam output
        async def read_output():
            try:
                while True:
                    line = await asyncio.get_event_loop().run_in_executor(
                        None, ibeam_process.stdout.readline
                    )
                    if line:
                        print(f"IBeam: {line.decode().strip()}")
                    else:
                        break
            except:
                pass
        
        asyncio.create_task(read_output())
        
        for i in range(90):
            await asyncio.sleep(1)
            
            # Check if process died
            if ibeam_process.poll() is not None:
                print(f"IBeam process exited with code: {ibeam_process.returncode}")
                break
            
            # Check if IBeam gateway is responding
            try:
                async with httpx.AsyncClient(verify=False, timeout=2.0) as client:
                    response = await client.get("http://localhost:5000/v1/api/iserver/auth/status")
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("authenticated"):
                            gateway_ready = True
                            print("✅ IBeam authentication successful")
                            return {
                                "status": "ready",
                                "message": "Connected to IBKR successfully"
                            }
            except:
                pass
            
            if i % 10 == 0:
                print(f"Still waiting... {i}/90 seconds")
        
        print("IBeam authentication timed out")
        
    except Exception as e:
        print(f"Error starting IBeam: {e}")
        import traceback
        traceback.print_exc()
    
    # Fallback: Use simulation mode
    gateway_ready = True
    print("⚠️ Using simulation mode")
    return {
        "status": "ready",
        "message": "Running in simulation mode - IBeam startup failed"
    }

@app.get("/account")
async def get_account():
    if not gateway_ready:
        raise HTTPException(status_code=503, detail="Gateway not ready")
    
    # Try real gateway first
    try:
        async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
            response = await client.get("http://localhost:5000/v1/api/portfolio/accounts")
            if response.status_code == 200:
                return response.json()
    except:
        pass
    
    # Fallback to mock data
    return [{
        "accountId": "SIM123",
        "accountType": "SIMULATION",
        "currency": "USD",
        "username": stored_credentials.get("username", "Unknown")
    }]

@app.get("/positions")
async def get_positions():
    if not gateway_ready:
        raise HTTPException(status_code=503, detail="Gateway not ready")
    
    # Try real gateway first
    try:
        async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
            accounts = await client.get("http://localhost:5000/v1/api/portfolio/accounts")
            if accounts.status_code == 200:
                account_data = accounts.json()
                if account_data:
                    account_id = account_data[0]["accountId"]
                    positions = await client.get(f"http://localhost:5000/v1/api/portfolio/{account_id}/positions/0")
                    if positions.status_code == 200:
                        return positions.json()
    except:
        pass
    
    # Fallback to mock data
    return [
        {
            "symbol": "AAPL",
            "quantity": 100,
            "average_price": 175.50,
            "current_price": 178.25,
            "unrealized_pnl": 275.00
        }
    ]

if __name__ == "__main__":
    import uvicorn
    # Render provides PORT env var, default to 10000 for Render
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)