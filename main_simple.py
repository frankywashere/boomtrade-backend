import os
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import httpx

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Credentials(BaseModel):
    username: str
    password: str
    account: Optional[str] = None

# Store session
session_data = {}
is_ready = False

@app.get("/health")
async def health():
    return {"status": "healthy", "gateway_ready": is_ready}

@app.post("/gateway/start")
async def start_gateway(credentials: Credentials):
    global is_ready, session_data
    
    # For testing - just store credentials and mark as ready
    session_data = {
        "username": credentials.username,
        "password": credentials.password,
        "account": credentials.account
    }
    
    # Simulate startup delay
    await asyncio.sleep(2)
    
    is_ready = True
    
    return {
        "status": "ready",
        "message": "Test mode - no real IBKR connection"
    }

@app.get("/account")
async def get_account():
    if not is_ready:
        raise HTTPException(status_code=503, detail="Not ready")
    
    # Return mock data
    return {
        "accountId": "TEST123",
        "accountType": "PAPER",
        "currency": "USD"
    }

@app.get("/positions")
async def get_positions():
    if not is_ready:
        raise HTTPException(status_code=503, detail="Not ready")
    
    # Return mock positions
    return [
        {
            "symbol": "AAPL",
            "quantity": 100,
            "average_price": 150.00,
            "current_price": 155.00,
            "unrealized_pnl": 500.00,
            "realized_pnl": 0
        }
    ]

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)