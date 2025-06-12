# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict
import uuid
import requests
import os
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from fastapi import BackgroundTasks, Query

app = FastAPI()

conf = ConnectionConfig(
    MAIL_USERNAME="letchaosprevailwtf@gmail.com",
    MAIL_PASSWORD="hppasrcrttsuculk",
    MAIL_FROM="anujsharma146201@gmail.com",
    MAIL_PORT=465,
    MAIL_SERVER="smtp.gmail.com",  # e.g., smtp.gmail.com
    MAIL_STARTTLS=False,
    MAIL_SSL_TLS=True,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
)

# In-memory store for pending trades (use a DB for production)
pending_trades: Dict[str, dict] = {}

# Load Upstox credentials from environment variables
UPSTOX_ACCESS_TOKEN = 'eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiI3NEFMNVoiLCJqdGkiOiI2ODRhZDMzOGI4ZWRlMDAyODkyMzUwMjciLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6dHJ1ZSwiaWF0IjoxNzQ5NzM0MjAwLCJpc3MiOiJ1ZGFwaS1nYXRld2F5LXNlcnZpY2UiLCJleHAiOjE3NDk3NjU2MDB9.FiGupxajSUzJIxb4G_3ouYK__cE-7yArfn1aAlCbFlo'
UPSTOX_BASE_URL = 'https://api.upstox.com/v2'  # Confirm latest endpoint

class TradeRequest(BaseModel):
    symbol: str
    action: str  # "BUY" or "SELL"
    qty: int

class ApprovalRequest(BaseModel):
    trade_id: str
    approve: bool

async def send_trade_email(trade_id: str, trade_data: dict, background_tasks: BackgroundTasks):
    approve_url = f"https://upstox-webhook-drus.onrender.com/approve?trade_id={trade_id}&approve=true"
    reject_url = f"https://upstox-webhook-drus.onrender.com/approve?trade_id={trade_id}&approve=false"

    html_content = f"""
    <h3>New Trade Pending Approval</h3>
    <p>Symbol: {trade_data['symbol']}</p>
    <p>Action: {trade_data['action']}</p>
    <p>Quantity: {trade_data['qty']}</p>
    <p>
        <a href="{approve_url}" style="padding:10px; background-color:green; color:white; text-decoration:none;">Approve</a>
        &nbsp;
        <a href="{reject_url}" style="padding:10px; background-color:red; color:white; text-decoration:none;">Reject</a>
    </p>
    """

    message = MessageSchema(
        subject="Trade Approval Request",
        recipients=["your_approval_email@example.com"],  # your email here
        body=html_content,
        subtype=MessageType.html,
    )
    fm = FastMail(conf)
    background_tasks.add_task(fm.send_message, message)

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
async def receive_trade_signal(trade: TradeRequest, background_tasks: BackgroundTasks):
    # Validate action
    if trade.action.upper() not in ['BUY', 'SELL']:
        raise HTTPException(status_code=400, detail="Invalid action, must be BUY or SELL")

    # Generate unique trade ID
    trade_id = str(uuid.uuid4())

    # Store trade request as pending
    pending_trades[trade_id] = trade.dict()

    await send_trade_email(trade_id, trade.dict(), background_tasks)
    # TODO: Send notification to yourself here (e.g., Telegram message, email)
    # For demo, just print
    print(f"New trade request pending approval: {trade_id} -> {trade.dict()}")

    return {"message": "Trade request received and pending approval", "trade_id": trade_id}

@app.post("/approve")
async def approve_trade_via_email(trade_id: str = Query(...), approve: bool = Query(...)):
     if trade_id not in pending_trades:
        return {"error": "Trade ID not found"}

     if approve:
        trade = pending_trades.pop(trade_id)
        order_response = place_order_upstox(
            symbol=trade['symbol'],
            transaction_type=trade['action'].upper(),
            quantity=trade['qty']
        )
        return {"message": "Order placed", "order_response": order_response}
     else:
        pending_trades.pop(trade_id)
        return {"message": "Trade rejected"}

@app.get("/pending_trades")
async def list_pending_trades():
    return pending_trades
