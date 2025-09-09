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
from contextlib import asynccontextmanager

# Environment variables
IBKR_USERNAME = os.getenv("IBKR_USERNAME", "")
IBKR_PASSWORD = os.getenv("IBKR_PASSWORD", "")
IBKR_ACCOUNT = os.getenv("IBKR_ACCOUNT", "")

# Global state
gateway_process = None
gateway_ready = False
ibeam_gateway_url = "https://localhost:5000"

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("FastAPI server starting...")
    yield
    # Shutdown
    global gateway_process
    if gateway_process:
        print("Shutting down gateway...")
        gateway_process.terminate()
        gateway_process.wait()

app = FastAPI(lifespan=lifespan)

# CORS for Swift app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health")
async def health():
    return {"status": "healthy", "gateway_ready": gateway_ready}

# Start IBeam gateway
@app.post("/gateway/start")
async def start_gateway(credentials: Credentials):
    global gateway_process, gateway_ready
    
    try:
        print(f"=== GATEWAY START REQUEST ===")
        print(f"Username: {credentials.username}")
        print(f"Account: {credentials.account}")
        print(f"Timestamp: {datetime.now()}")
        
        # Write credentials to environment file for IBeam
        env_content = f"""IBEAM_ACCOUNT={credentials.username}
IBEAM_PASSWORD={credentials.password}
"""
        if credentials.account:
            env_content += f"IBEAM_TRADING_MODE=paper\n"
        
        with open("/tmp/ibeam.env", "w") as f:
            f.write(env_content)
        
        # Start IBeam process
        env = os.environ.copy()
        env.update({
            "IBEAM_ACCOUNT": credentials.username,
            "IBEAM_PASSWORD": credentials.password,
            "IBEAM_GATEWAY_DIR": "/tmp/clientportal",
            "IBEAM_LOG_LEVEL": "INFO"
        })
        
        # Launch IBeam
        print("Launching IBeam process...")
        gateway_process = subprocess.Popen(
            ["python", "-m", "ibeam", "gateway", "start", "--config", "ibeam_config.yml"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        print(f"IBeam process started with PID: {gateway_process.pid}")
        print("Waiting for gateway to initialize...")
        
        # Wait for gateway to be ready
        max_attempts = 90  # 90 * 2 = 180 seconds max
        for i in range(max_attempts):
            try:
                async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
                    # Try to hit the gateway status endpoint
                    response = await client.get(f"{ibeam_gateway_url}/v1/api/iserver/auth/status")
                    
                    if response.status_code == 200:
                        data = response.json()
                        print(f"Gateway response: {data}")
                        
                        # Check if authenticated
                        if data.get("authenticated", False):
                            gateway_ready = True
                            print("Gateway is ready and authenticated!")
                            return {"status": "ready", "message": "Gateway started successfully"}
                        elif data.get("competing", False):
                            return {"status": "error", "message": "Another session is active. Please logout from other sessions."}
                        else:
                            print(f"Gateway not yet authenticated, attempt {i+1}/{max_attempts}")
                    else:
                        print(f"Gateway returned status {response.status_code}, attempt {i+1}/{max_attempts}")
            except Exception as e:
                print(f"Gateway not responding yet ({i+1}/{max_attempts}): {str(e)}")
            
            await asyncio.sleep(2)
        
        return {"status": "timeout", "message": "Gateway startup timeout. Please check your credentials."}
        
    except Exception as e:
        print(f"Gateway start error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Get account info
@app.get("/account")
async def get_account():
    if not gateway_ready:
        raise HTTPException(status_code=503, detail="Gateway not ready")
    
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(f"{ibeam_gateway_url}/v1/api/portfolio/accounts")
        return response.json()

# Get positions
@app.get("/positions")
async def get_positions():
    if not gateway_ready:
        raise HTTPException(status_code=503, detail="Gateway not ready")
    
    async with httpx.AsyncClient(verify=False) as client:
        # Get accounts first
        accounts_resp = await client.get(f"{ibeam_gateway_url}/v1/api/portfolio/accounts")
        accounts = accounts_resp.json()
        
        if accounts:
            account_id = accounts[0]["accountId"]
            response = await client.get(f"{ibeam_gateway_url}/v1/api/portfolio/{account_id}/positions/0")
            return response.json()
        return []

# Search for option contracts
@app.get("/options/search/{symbol}")
async def search_options(symbol: str):
    if not gateway_ready:
        raise HTTPException(status_code=503, detail="Gateway not ready")
    
    async with httpx.AsyncClient(verify=False) as client:
        # Search for symbol
        search_resp = await client.get(
            f"{ibeam_gateway_url}/v1/api/iserver/secdef/search",
            params={"symbol": symbol}
        )
        results = search_resp.json()
        
        if results:
            conid = results[0]["conid"]
            # Get option chains
            chains_resp = await client.get(
                f"{ibeam_gateway_url}/v1/api/iserver/secdef/option-chains",
                params={"conid": conid}
            )
            return chains_resp.json()
        return []

# Get option chain
@app.get("/options/chain/{symbol}/{expiry}")
async def get_option_chain(symbol: str, expiry: str):
    if not gateway_ready:
        raise HTTPException(status_code=503, detail="Gateway not ready")
    
    async with httpx.AsyncClient(verify=False) as client:
        # Search for symbol
        search_resp = await client.get(
            f"{ibeam_gateway_url}/v1/api/iserver/secdef/search",
            params={"symbol": symbol}
        )
        results = search_resp.json()
        
        if results:
            conid = results[0]["conid"]
            # Get strikes for expiry
            strikes_resp = await client.get(
                f"{ibeam_gateway_url}/v1/api/iserver/secdef/strikes",
                params={"conid": conid, "expiry": expiry}
            )
            return strikes_resp.json()
        return []

# Place stock order
@app.post("/order/stock")
async def place_stock_order(order: Order):
    if not gateway_ready:
        raise HTTPException(status_code=503, detail="Gateway not ready")
    
    async with httpx.AsyncClient(verify=False) as client:
        # Get accounts
        accounts_resp = await client.get(f"{ibeam_gateway_url}/v1/api/portfolio/accounts")
        accounts = accounts_resp.json()
        
        if not accounts:
            raise HTTPException(status_code=404, detail="No accounts found")
        
        account_id = accounts[0]["accountId"]
        
        # Search for contract
        search_resp = await client.get(
            f"{ibeam_gateway_url}/v1/api/iserver/secdef/search",
            params={"symbol": order.symbol}
        )
        results = search_resp.json()
        
        if not results:
            raise HTTPException(status_code=404, detail="Symbol not found")
        
        conid = results[0]["conid"]
        
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
            f"{ibeam_gateway_url}/v1/api/iserver/account/{account_id}/orders",
            json={"orders": [order_data]}
        )
        
        return response.json()

# Place option order
@app.post("/order/option")
async def place_option_order(order: OptionOrder):
    if not gateway_ready:
        raise HTTPException(status_code=503, detail="Gateway not ready")
    
    async with httpx.AsyncClient(verify=False) as client:
        # Get accounts
        accounts_resp = await client.get(f"{ibeam_gateway_url}/v1/api/portfolio/accounts")
        accounts = accounts_resp.json()
        
        if not accounts:
            raise HTTPException(status_code=404, detail="No accounts found")
        
        account_id = accounts[0]["accountId"]
        
        # Build option symbol
        option_symbol = f"{order.symbol} {order.expiry} {order.right} {order.strike}"
        
        # Search for option contract
        search_resp = await client.get(
            f"{ibeam_gateway_url}/v1/api/iserver/secdef/search",
            params={"symbol": option_symbol}
        )
        results = search_resp.json()
        
        if not results:
            raise HTTPException(status_code=404, detail="Option contract not found")
        
        conid = results[0]["conid"]
        
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
            f"{ibeam_gateway_url}/v1/api/iserver/account/{account_id}/orders",
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
        search_resp = await client.get(
            f"{ibeam_gateway_url}/v1/api/iserver/secdef/search",
            params={"symbol": symbol}
        )
        results = search_resp.json()
        
        if not results:
            raise HTTPException(status_code=404, detail="Symbol not found")
        
        conid = results[0]["conid"]
        
        # Get market data
        response = await client.get(
            f"{ibeam_gateway_url}/v1/api/iserver/marketdata/snapshot",
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)