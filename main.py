import os
import asyncio
import subprocess
import time
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import httpx
import json
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
gateway_process = None
gateway_ready = False
ibeam_url = "https://localhost:5000/v1/api"
session_data = {}

class Credentials(BaseModel):
    username: str
    password: str
    account: Optional[str] = None

class Order(BaseModel):
    symbol: str
    quantity: int
    order_type: str  # MKT, LMT, STP, etc.
    side: str  # BUY, SELL
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "DAY"  # DAY, GTC, IOC, FOK

class OptionOrder(BaseModel):
    symbol: str  # Underlying
    expiry: str  # YYYYMMDD
    strike: float
    right: str  # C or P
    quantity: int
    order_type: str
    side: str
    limit_price: Optional[float] = None

# Startup event
@app.on_event("startup")
async def startup_event():
    print("FastAPI server started. IBeam will start on first request.")

# Health check
@app.get("/health")
async def health():
    return {"status": "healthy", "gateway_ready": gateway_ready}

# Start IBeam gateway
@app.post("/gateway/start")
async def start_gateway(credentials: Credentials):
    global gateway_process, gateway_ready, session_data
    
    try:
        # Store credentials for IBeam
        session_data = {
            "username": credentials.username,
            "password": credentials.password,
            "account": credentials.account
        }
        
        # Create IBeam config
        config = {
            "username": credentials.username,
            "password": credentials.password,
            "account": credentials.account,
            "gateway_start": True,
            "gateway_dir": "/tmp/clientportal",
            "cache_2fa": True
        }
        
        with open("/tmp/ibeam_config.yml", "w") as f:
            json.dump(config, f)
        
        # Start IBeam
        gateway_process = subprocess.Popen([
            "python", "-m", "ibeam", 
            "--config", "/tmp/ibeam_config.yml"
        ])
        
        # Wait for gateway to be ready (check port 5000)
        max_attempts = 60
        for i in range(max_attempts):
            try:
                async with httpx.AsyncClient(verify=False) as client:
                    response = await client.get(f"{ibeam_url}/iserver/auth/status")
                    if response.status_code == 200:
                        gateway_ready = True
                        return {"status": "ready", "message": "Gateway started successfully"}
            except:
                pass
            await asyncio.sleep(2)
        
        return {"status": "timeout", "message": "Gateway startup timeout"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get account info
@app.get("/account")
async def get_account():
    if not gateway_ready:
        raise HTTPException(status_code=503, detail="Gateway not ready")
    
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(f"{ibeam_url}/iserver/accounts")
        return response.json()

# Get positions
@app.get("/positions")
async def get_positions():
    if not gateway_ready:
        raise HTTPException(status_code=503, detail="Gateway not ready")
    
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(f"{ibeam_url}/iserver/positions")
        return response.json()

# Search for option contracts
@app.get("/options/search/{symbol}")
async def search_options(symbol: str):
    if not gateway_ready:
        raise HTTPException(status_code=503, detail="Gateway not ready")
    
    async with httpx.AsyncClient(verify=False) as client:
        # Get contract ID for underlying
        search = await client.get(f"{ibeam_url}/iserver/secdef/search", params={"symbol": symbol})
        contracts = search.json()
        
        if not contracts:
            raise HTTPException(status_code=404, detail="Symbol not found")
        
        conid = contracts[0]["conid"]
        
        # Get option chains
        chains = await client.get(f"{ibeam_url}/iserver/secdef/option-chains", params={"conid": conid})
        return chains.json()

# Get option chain
@app.get("/options/chain/{symbol}/{expiry}")
async def get_option_chain(symbol: str, expiry: str):
    if not gateway_ready:
        raise HTTPException(status_code=503, detail="Gateway not ready")
    
    async with httpx.AsyncClient(verify=False) as client:
        # Implementation for specific expiry chain
        search = await client.get(f"{ibeam_url}/iserver/secdef/search", params={"symbol": symbol})
        contracts = search.json()
        
        if not contracts:
            raise HTTPException(status_code=404, detail="Symbol not found")
        
        conid = contracts[0]["conid"]
        
        # Get strikes for expiry
        strikes = await client.get(
            f"{ibeam_url}/iserver/secdef/strikes",
            params={"conid": conid, "expiry": expiry}
        )
        return strikes.json()

# Place stock order
@app.post("/order/stock")
async def place_stock_order(order: Order):
    if not gateway_ready:
        raise HTTPException(status_code=503, detail="Gateway not ready")
    
    async with httpx.AsyncClient(verify=False) as client:
        # Get account ID
        accounts = await client.get(f"{ibeam_url}/iserver/accounts")
        account_id = accounts.json()[0]
        
        # Search for contract
        search = await client.get(f"{ibeam_url}/iserver/secdef/search", params={"symbol": order.symbol})
        contracts = search.json()
        
        if not contracts:
            raise HTTPException(status_code=404, detail="Symbol not found")
        
        conid = contracts[0]["conid"]
        
        # Build order
        order_data = {
            "acctId": account_id,
            "conid": conid,
            "orderType": order.order_type,
            "side": order.side,
            "quantity": order.quantity,
            "tif": order.time_in_force
        }
        
        if order.limit_price:
            order_data["price"] = order.limit_price
        if order.stop_price:
            order_data["auxPrice"] = order.stop_price
        
        # Place order
        response = await client.post(
            f"{ibeam_url}/iserver/account/{account_id}/orders",
            json={"orders": [order_data]}
        )
        
        return response.json()

# Place option order
@app.post("/order/option")
async def place_option_order(order: OptionOrder):
    if not gateway_ready:
        raise HTTPException(status_code=503, detail="Gateway not ready")
    
    async with httpx.AsyncClient(verify=False) as client:
        # Get account ID
        accounts = await client.get(f"{ibeam_url}/iserver/accounts")
        account_id = accounts.json()[0]
        
        # Build option symbol (e.g., "AAPL 20240115 C 150")
        option_symbol = f"{order.symbol} {order.expiry} {order.right} {order.strike}"
        
        # Search for option contract
        search = await client.get(f"{ibeam_url}/iserver/secdef/search", params={"symbol": option_symbol})
        contracts = search.json()
        
        if not contracts:
            raise HTTPException(status_code=404, detail="Option contract not found")
        
        conid = contracts[0]["conid"]
        
        # Build order
        order_data = {
            "acctId": account_id,
            "conid": conid,
            "orderType": order.order_type,
            "side": order.side,
            "quantity": order.quantity,
            "tif": "DAY"
        }
        
        if order.limit_price:
            order_data["price"] = order.limit_price
        
        # Place order
        response = await client.post(
            f"{ibeam_url}/iserver/account/{account_id}/orders",
            json={"orders": [order_data]}
        )
        
        return response.json()

# Get market data
@app.get("/marketdata/{symbol}")
async def get_market_data(symbol: str):
    if not gateway_ready:
        raise HTTPException(status_code=503, detail="Gateway not ready")
    
    async with httpx.AsyncClient(verify=False) as client:
        # Search for contract
        search = await client.get(f"{ibeam_url}/iserver/secdef/search", params={"symbol": symbol})
        contracts = search.json()
        
        if not contracts:
            raise HTTPException(status_code=404, detail="Symbol not found")
        
        conid = contracts[0]["conid"]
        
        # Get market data
        response = await client.get(
            f"{ibeam_url}/iserver/marketdata/snapshot",
            params={"conids": conid, "fields": "31,84,85,86,87,88"}
        )
        
        return response.json()

# WebSocket for real-time data
@app.websocket("/ws/marketdata")
async def websocket_market_data(websocket: WebSocket):
    await websocket.accept()
    
    try:
        while True:
            # Receive symbol from client
            data = await websocket.receive_json()
            symbol = data.get("symbol")
            
            if symbol:
                # Get real-time data
                market_data = await get_market_data(symbol)
                await websocket.send_json(market_data)
            
            await asyncio.sleep(1)  # Rate limiting
            
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()

# Shutdown gateway on exit
@app.on_event("shutdown")
async def shutdown_event():
    global gateway_process
    if gateway_process:
        gateway_process.terminate()
        gateway_process.wait()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)