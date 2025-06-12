# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict
import uuid
import requests
import os

app = FastAPI()

# In-memory store for pending trades (use a DB for production)
pending_trades: Dict[str, dict] = {}

# Load Upstox credentials from environment variables
UPSTOX_ACCESS_TOKEN = os.getenv('UPSTOX_ACCESS_TOKEN')
UPSTOX_BASE_URL = 'https://api.upstox.com/v2'  # Confirm latest endpoint

class TradeRequest(BaseModel):
    symbol: str
    action: str  # "BUY" or "SELL"
    qty: int

class ApprovalRequest(BaseModel):
    trade_id: str
    approve: bool

def place_order_upstox(symbol: str, transaction_type: str, quantity: int, order_type='MARKET', product='CNC'):
    url = f"{UPSTOX_BASE_URL}/order/place"
    headers = {
        'Authorization': f'Bearer {UPSTOX_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    payload = {
        "symbol": symbol,
        "transaction_type": transaction_type,
        "quantity": quantity,
        "order_type": order_type,
        "product": product
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

@app.post("/webhook")
async def receive_trade_signal(trade: TradeRequest):
    # Validate action
    if trade.action.upper() not in ['BUY', 'SELL']:
        raise HTTPException(status_code=400, detail="Invalid action, must be BUY or SELL")

    # Generate unique trade ID
    trade_id = str(uuid.uuid4())

    # Store trade request as pending
    pending_trades[trade_id] = trade.dict()

    # TODO: Send notification to yourself here (e.g., Telegram message, email)
    # For demo, just print
    print(f"New trade request pending approval: {trade_id} -> {trade.dict()}")

    return {"message": "Trade request received and pending approval", "trade_id": trade_id}

@app.post("/approve")
async def approve_trade(approval: ApprovalRequest):
    trade_id = approval.trade_id
    if trade_id not in pending_trades:
        raise HTTPException(status_code=404, detail="Trade ID not found")

    if approval.approve:
        trade = pending_trades.pop(trade_id)
        # Place order on Upstox
        order_response = place_order_upstox(
            symbol=trade['symbol'],
            transaction_type=trade['action'].upper(),
            quantity=trade['qty']
        )
        return {"message": "Order placed", "order_response": order_response}
    else:
        # Reject trade
        pending_trades.pop(trade_id)
        return {"message": "Trade rejected"}

@app.get("/pending_trades")
async def list_pending_trades():
    return pending_trades
