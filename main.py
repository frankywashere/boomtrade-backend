"""
BoomTrade Backend - Connects to local TWS/IB Gateway
No browser automation, no Docker, just clean API connection
"""
import os
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from ib_insync import IB, Stock, Option, Order, MarketOrder, LimitOrder, Contract
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BoomTrade Backend")

# CORS configuration for iOS app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global IB connection
ib = IB()
connected = False

# Configuration
TWS_HOST = os.getenv("TWS_HOST", "127.0.0.1")  # localhost
TWS_PORT = int(os.getenv("TWS_PORT", "7497"))  # 7497 for paper, 7496 for live
TWS_CLIENT_ID = int(os.getenv("TWS_CLIENT_ID", "1"))

# Request Models
class ConnectionConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 7497  # Default to paper trading
    client_id: int = 1
    
class StockOrder(BaseModel):
    symbol: str
    quantity: int
    order_type: str  # MKT, LMT, STP, STP_LMT
    action: str  # BUY, SELL
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    
class OptionOrder(BaseModel):
    symbol: str
    expiry: str  # YYYYMMDD
    strike: float
    right: str  # C or P
    quantity: int
    order_type: str
    action: str  # BUY, SELL
    limit_price: Optional[float] = None

# Endpoints
@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "connected": connected,
        "connection": {
            "host": TWS_HOST,
            "port": TWS_PORT,
            "type": "paper" if TWS_PORT == 7497 else "live"
        }
    }

@app.post("/connect")
async def connect_to_tws(config: ConnectionConfig):
    """Connect to TWS/IB Gateway running locally"""
    global connected
    
    try:
        # Disconnect if already connected
        if ib.isConnected():
            ib.disconnect()
            
        logger.info(f"Connecting to TWS at {config.host}:{config.port}")
        
        # Connect to TWS/IB Gateway
        await ib.connectAsync(
            host=config.host,
            port=config.port,
            clientId=config.client_id,
            timeout=10
        )
        
        connected = True
        
        # Get account info
        accounts = ib.managedAccounts()
        
        # Check market data subscriptions
        account = accounts[0] if accounts else None
        account_values = ib.accountValues(account) if account else []
        
        return {
            "status": "connected",
            "accounts": accounts,
            "server_version": ib.serverVersion(),
            "connection_time": ib.connectionTime(),
            "market_data_available": any(av.tag == "MarketDataType" for av in account_values)
        }
        
    except Exception as e:
        logger.error(f"Connection failed: {str(e)}")
        connected = False
        raise HTTPException(status_code=503, detail=f"Failed to connect to TWS: {str(e)}")

@app.post("/disconnect")
async def disconnect_from_tws():
    """Disconnect from TWS/IB Gateway"""
    global connected
    
    if ib.isConnected():
        ib.disconnect()
    
    connected = False
    return {"status": "disconnected"}

@app.get("/account")
async def get_account_info():
    """Get account information"""
    if not ib.isConnected():
        raise HTTPException(status_code=503, detail="Not connected to TWS")
    
    accounts = ib.managedAccounts()
    if not accounts:
        return {"error": "No accounts found"}
    
    account = accounts[0]
    account_values = ib.accountValues(account)
    account_summary = ib.accountSummary(account)
    
    # Extract key values
    summary = {}
    for av in account_values:
        if av.tag in ["NetLiquidation", "TotalCashValue", "BuyingPower", "AvailableFunds"]:
            summary[av.tag] = av.value
    
    return {
        "account": account,
        "summary": summary,
        "currency": account_values[0].currency if account_values else "USD",
        "account_type": "Paper" if "DU" in account else "Live"
    }

@app.get("/positions")
async def get_positions():
    """Get current positions"""
    if not ib.isConnected():
        raise HTTPException(status_code=503, detail="Not connected to TWS")
    
    positions = ib.positions()
    
    return [
        {
            "symbol": pos.contract.symbol,
            "sec_type": pos.contract.secType,
            "quantity": pos.position,
            "average_cost": pos.avgCost,
            "market_value": pos.marketValue if hasattr(pos, 'marketValue') else None,
            "unrealized_pnl": pos.unrealizedPNL if hasattr(pos, 'unrealizedPNL') else None
        }
        for pos in positions
    ]

@app.get("/orders")
async def get_orders():
    """Get open orders"""
    if not ib.isConnected():
        raise HTTPException(status_code=503, detail="Not connected to TWS")
    
    orders = ib.openOrders()
    
    return [
        {
            "order_id": order.orderId,
            "symbol": order.contract.symbol,
            "action": order.action,
            "quantity": order.totalQuantity,
            "order_type": order.orderType,
            "status": order.status if hasattr(order, 'status') else "Unknown",
            "limit_price": order.lmtPrice if hasattr(order, 'lmtPrice') else None
        }
        for order in orders
    ]

@app.post("/order/stock")
async def place_stock_order(order: StockOrder):
    """Place a stock order"""
    if not ib.isConnected():
        raise HTTPException(status_code=503, detail="Not connected to TWS")
    
    try:
        # Create contract
        contract = Stock(order.symbol, 'SMART', 'USD')
        
        # Qualify the contract
        ib.qualifyContracts(contract)
        
        # Create order based on type
        if order.order_type == "MKT":
            ib_order = MarketOrder(order.action, order.quantity)
        elif order.order_type == "LMT":
            if not order.limit_price:
                raise ValueError("Limit price required for limit orders")
            ib_order = LimitOrder(order.action, order.quantity, order.limit_price)
        else:
            raise ValueError(f"Unsupported order type: {order.order_type}")
        
        # Place order
        trade = ib.placeOrder(contract, ib_order)
        
        # Wait a moment for order to be acknowledged
        await asyncio.sleep(0.5)
        
        return {
            "order_id": trade.order.orderId,
            "status": trade.orderStatus.status,
            "contract": order.symbol,
            "action": order.action,
            "quantity": order.quantity
        }
        
    except Exception as e:
        logger.error(f"Order failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/order/option")
async def place_option_order(order: OptionOrder):
    """Place an option order"""
    if not ib.isConnected():
        raise HTTPException(status_code=503, detail="Not connected to TWS")
    
    try:
        # Create option contract
        contract = Option(
            order.symbol,
            order.expiry,
            order.strike,
            order.right,
            'SMART'
        )
        
        # Qualify the contract
        ib.qualifyContracts(contract)
        
        # Create order
        if order.order_type == "MKT":
            ib_order = MarketOrder(order.action, order.quantity)
        elif order.order_type == "LMT":
            if not order.limit_price:
                raise ValueError("Limit price required for limit orders")
            ib_order = LimitOrder(order.action, order.quantity, order.limit_price)
        else:
            raise ValueError(f"Unsupported order type: {order.order_type}")
        
        # Place order
        trade = ib.placeOrder(contract, ib_order)
        
        # Wait for acknowledgment
        await asyncio.sleep(0.5)
        
        return {
            "order_id": trade.order.orderId,
            "status": trade.orderStatus.status,
            "contract": f"{order.symbol} {order.expiry} {order.strike}{order.right}",
            "action": order.action,
            "quantity": order.quantity
        }
        
    except Exception as e:
        logger.error(f"Option order failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/market-data/{symbol}")
async def get_market_data(symbol: str):
    """Get real-time market data for a symbol"""
    if not ib.isConnected():
        raise HTTPException(status_code=503, detail="Not connected to TWS")
    
    try:
        contract = Stock(symbol, 'SMART', 'USD')
        ib.qualifyContracts(contract)
        
        # Request market data
        ticker = ib.reqMktData(contract, '', False, False)
        
        # Wait for data
        await asyncio.sleep(1)
        
        return {
            "symbol": symbol,
            "bid": ticker.bid,
            "ask": ticker.ask,
            "last": ticker.last,
            "volume": ticker.volume,
            "high": ticker.high,
            "low": ticker.low,
            "close": ticker.close
        }
        
    except Exception as e:
        logger.error(f"Market data request failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.websocket("/ws/market-data")
async def websocket_market_data(websocket: WebSocket):
    """WebSocket for streaming market data"""
    await websocket.accept()
    
    if not ib.isConnected():
        await websocket.send_json({"error": "Not connected to TWS"})
        await websocket.close()
        return
    
    try:
        while True:
            data = await websocket.receive_json()
            symbol = data.get("symbol")
            
            if symbol:
                contract = Stock(symbol, 'SMART', 'USD')
                ib.qualifyContracts(contract)
                ticker = ib.reqMktData(contract, '', False, False)
                
                # Stream updates
                while True:
                    await asyncio.sleep(0.5)
                    await websocket.send_json({
                        "symbol": symbol,
                        "bid": ticker.bid,
                        "ask": ticker.ask,
                        "last": ticker.last,
                        "timestamp": datetime.now().isoformat()
                    })
                    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await websocket.close()

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("BoomTrade Backend Starting...")
    logger.info(f"Default connection: {TWS_HOST}:{TWS_PORT}")
    logger.info("Run TWS or IB Gateway locally before connecting")
    
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if ib.isConnected():
        ib.disconnect()
    logger.info("BoomTrade Backend Stopped")

if __name__ == "__main__":
    import uvicorn
    # Run locally on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)