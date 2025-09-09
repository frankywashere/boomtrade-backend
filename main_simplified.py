import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

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

class GatewayStatus(BaseModel):
    status: str
    message: str

@app.get("/health")
async def health():
    return {"status": "healthy", "gateway_ready": gateway_ready}

@app.post("/gateway/start")
async def start_gateway(credentials: Credentials):
    global gateway_ready, stored_credentials
    
    print(f"=== GATEWAY START REQUEST ===")
    print(f"Username: {credentials.username}")
    print(f"Account: {credentials.account}")
    print(f"Timestamp: {datetime.now()}")
    
    # Store credentials for future use
    stored_credentials = {
        "username": credentials.username,
        "password": credentials.password,
        "account": credentials.account
    }
    
    # For now, just mark as ready after validation
    if credentials.username and credentials.password:
        gateway_ready = True
        print("Gateway marked as ready (simulation mode)")
        return {
            "status": "ready",
            "message": "Connected in simulation mode - IBeam integration pending"
        }
    else:
        return {
            "status": "error",
            "message": "Invalid credentials"
        }

@app.get("/account")
async def get_account():
    if not gateway_ready:
        raise HTTPException(status_code=503, detail="Gateway not ready")
    
    return {
        "accountId": "SIM123",
        "accountType": "SIMULATION",
        "currency": "USD",
        "username": stored_credentials.get("username", "Unknown")
    }

@app.get("/positions")
async def get_positions():
    if not gateway_ready:
        raise HTTPException(status_code=503, detail="Gateway not ready")
    
    # Return mock positions for testing
    return [
        {
            "symbol": "AAPL",
            "quantity": 100,
            "average_price": 175.50,
            "current_price": 178.25,
            "unrealized_pnl": 275.00,
            "realized_pnl": 0
        },
        {
            "symbol": "TSLA", 
            "quantity": 50,
            "average_price": 240.00,
            "current_price": 245.50,
            "unrealized_pnl": 275.00,
            "realized_pnl": 0
        }
    ]

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting simplified server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)