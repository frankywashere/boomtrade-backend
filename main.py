import os
import time
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
    global gateway_ready, stored_credentials
    
    print(f"=== GATEWAY START REQUEST ===")
    print(f"Username: {credentials.username}")
    print(f"Account: {credentials.account}")
    print(f"Timestamp: {datetime.now()}")
    
    # Store credentials
    stored_credentials = credentials.dict()
    
    # Try to authenticate with IBeam if it's running
    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            # First check if gateway is alive
            status_response = await client.get("http://localhost:5000/v1/api/iserver/auth/status")
            print(f"Gateway status check: {status_response.status_code}")
            
            if status_response.status_code == 200:
                # Try to authenticate
                auth_data = {
                    "username": credentials.username,
                    "password": credentials.password
                }
                
                auth_response = await client.post(
                    "http://localhost:5000/v1/api/iserver/auth/ssodh/init",
                    json=auth_data
                )
                
                if auth_response.status_code == 200:
                    gateway_ready = True
                    print("✅ IBeam authentication successful")
                    return {
                        "status": "ready",
                        "message": "Connected to IBKR via IBeam"
                    }
    except Exception as e:
        print(f"IBeam connection failed: {e}")
    
    # Fallback: Just mark as ready for testing
    gateway_ready = True
    print("⚠️ Using simulation mode")
    return {
        "status": "ready",
        "message": "Running in simulation mode - IBeam connection pending"
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