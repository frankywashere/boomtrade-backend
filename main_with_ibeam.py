import os
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import httpx
from datetime import datetime
from ibeam import IBeam

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global IBeam instance
ibeam_instance = None
gateway_ready = False

class Credentials(BaseModel):
    username: str
    password: str
    account: Optional[str] = None

@app.get("/health")
async def health():
    return {"status": "healthy", "gateway_ready": gateway_ready}

@app.post("/gateway/start")
async def start_gateway(credentials: Credentials):
    global ibeam_instance, gateway_ready
    
    print(f"=== GATEWAY START REQUEST ===")
    print(f"Username: {credentials.username}")
    print(f"Timestamp: {datetime.now()}")
    
    try:
        # Configure IBeam
        os.environ['IBEAM_ACCOUNT'] = credentials.username
        os.environ['IBEAM_PASSWORD'] = credentials.password
        
        # Initialize IBeam
        print("Initializing IBeam...")
        ibeam_instance = IBeam(
            account=credentials.username,
            password=credentials.password,
            gateway_dir='/srv/clientportal.gw',
            cache_dir='/tmp/ibeam_cache'
        )
        
        # Start and authenticate
        print("Starting IBeam authentication...")
        success = await asyncio.to_thread(ibeam_instance.start_and_authenticate)
        
        if success:
            gateway_ready = True
            print("✅ IBeam authentication successful!")
            return {"status": "ready", "message": "Connected to IBKR successfully"}
        else:
            print("❌ IBeam authentication failed")
            return {"status": "error", "message": "Authentication failed"}
            
    except Exception as e:
        print(f"❌ Error starting gateway: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.get("/account")
async def get_account():
    if not gateway_ready:
        raise HTTPException(status_code=503, detail="Gateway not ready")
    
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get("https://localhost:5000/v1/api/portfolio/accounts")
        return response.json()

@app.get("/positions")
async def get_positions():
    if not gateway_ready:
        raise HTTPException(status_code=503, detail="Gateway not ready")
    
    async with httpx.AsyncClient(verify=False) as client:
        accounts = await client.get("https://localhost:5000/v1/api/portfolio/accounts")
        account_data = accounts.json()
        
        if account_data:
            account_id = account_data[0]["accountId"]
            positions = await client.get(f"https://localhost:5000/v1/api/portfolio/{account_id}/positions/0")
            return positions.json()
    return []

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting server with IBeam integration on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)