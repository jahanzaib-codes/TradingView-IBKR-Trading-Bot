import os
import sys
import asyncio
from datetime import datetime, timedelta
import pytz
from logger import LOGGER as log
from ib_insync import IB, MarketOrder, LimitOrder, Stock, util
from sanic import Sanic, response
from contract import get_stock_contract

# Create Sanic object
app = Sanic(__name__)

# IB constants
HOST = "127.0.0.1"
DEMO_PORT = 7497  # Paper trading
LIVE_PORT = 7496  # Live trading
POSITION_SIZE = 1  # Default quantity

# Global IB instance
ib: IB = None

# Positions tracking
positions = {}

# ET timezone with fallback
try:
    et_tz = pytz.timezone('US/Eastern')
except pytz.exceptions.PytzError:
    log.error("Timezone data missing. Install 'tzdata' with 'pip install tzdata'")
    et_tz = None

def is_pre_market() -> bool:
    if not et_tz:
        return False  # Fallback to market orders if timezone fails
    now_et = datetime.now(et_tz)
    start = now_et.replace(hour=4, minute=0, second=0, microsecond=0)
    end = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    return start <= now_et < end

def is_regular_hours() -> bool:
    if not et_tz:
        return True  # Default to market orders
    now_et = datetime.now(et_tz)
    start = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    end = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    return start <= now_et < end

def is_post_market() -> bool:
    if not et_tz:
        return False
    now_et = datetime.now(et_tz)
    start = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    end = now_et.replace(hour=20, minute=0, second=0, microsecond=0)
    return start <= now_et < end

async def update_positions():
    global positions
    pos_list = ib.positions()
    positions = {pos.contract.symbol: {'qty': pos.position, 'side': 'long' if pos.position > 0 else 'short' if pos.position < 0 else 'none'} 
                 for pos in pos_list if pos.contract.secType == 'STK'}

async def get_current_price(ticker: str, is_ask: bool = True) -> float:
    contract = get_stock_contract(ticker)
    ib.reqMktData(contract, '', False, False)
    await asyncio.sleep(1)
    ticker_data = ib.ticker(contract)
    price = ticker_data.ask if is_ask and ticker_data.ask > 0 else ticker_data.bid
    ib.cancelMktData(contract)
    return price if price > 0 else 0.0

def create_order(action: str, qty: int, limit_price: float = None) -> LimitOrder or MarketOrder:
    outside_rth = not is_regular_hours()
    if limit_price:
        order = LimitOrder(action, qty, limit_price, outsideRth=outside_rth)
    else:
        order = MarketOrder(action, qty, outsideRth=outside_rth)
    return order

async def monitor_and_resubmit_order(order_id: int, symbol: str, action: str, submit_time: datetime):
    while True:
        await asyncio.sleep(60)
        order_status = ib.orderStatus(order_id)
        if order_status.status in ['Filled', 'Cancelled']:
            log.info(f"Order {order_id} for {symbol} {action}: {order_status.status}")
            break
        if datetime.now() - submit_time > timedelta(minutes=3):
            new_price = await get_current_price(symbol, is_ask=(action == 'BUY'))
            if new_price <= 0:
                log.error(f"Failed to get valid price for {symbol}, cancelling order")
                ib.cancelOrder(ib.orders[order_id])
                break
            new_order = create_order(action, POSITION_SIZE, new_price)
            new_trade = ib.placeOrder(ib.orders[order_id].contract, new_order)
            log.info(f"Resubmitted {action} order for {symbol} at {new_price}")
            submit_time = datetime.now()

@app.route('/')
async def root(request):
    return response.text('Trading Bot Online')

@app.route('/webhook', methods=['POST'])
async def webhook(request):
    global ib
    data = request.json
    signal_action = data.get('action', '').upper().strip().replace('{{', '').replace('}}', '')
    symbol = data.get('symbol', '').upper().strip().replace('{{', '').replace('}}', '')

    if not signal_action or not symbol:
        log.error(f"Invalid signal: {data}")
        return response.json({"status": "error", "message": "Invalid payload"})

    if signal_action not in ['BUY', 'SELL']:
        log.error(f"Invalid action: {signal_action}. Expected BUY or SELL")
        return response.json({"status": "error", "message": f"Invalid action: {signal_action}"})

    await update_positions()
    current_pos = positions.get(symbol, {'qty': 0, 'side': 'none'})

    qty_to_trade = abs(current_pos['qty']) or POSITION_SIZE
    contract = get_stock_contract(symbol)
    if signal_action == 'BUY':
        if current_pos['side'] == 'short':
            close_order = create_order('BUY', qty_to_trade)
            ib.placeOrder(contract, close_order)
            log.info(f"Closed short {qty_to_trade} {symbol}")
        trade_order = create_order('BUY', qty_to_trade)
        if is_pre_market() or is_post_market():
            ask_price = await get_current_price(symbol, is_ask=True)
            if ask_price <= 0:
                log.error(f"Invalid ask price for {symbol}")
                return response.json({"status": "error", "message": "Invalid price"})
            trade_order = create_order('BUY', qty_to_trade, ask_price)
            trade = ib.placeOrder(contract, trade_order)
            asyncio.create_task(monitor_and_resubmit_order(trade.order.orderId, symbol, 'BUY', datetime.now()))
        else:
            trade = ib.placeOrder(contract, trade_order)
        log.info(f"Executed BUY {qty_to_trade} {symbol}. Trade: {trade}")
    elif signal_action == 'SELL':
        if current_pos['side'] == 'long':
            close_order = create_order('SELL', qty_to_trade)
            ib.placeOrder(contract, close_order)
            log.info(f"Closed long {qty_to_trade} {symbol}")
        trade_order = create_order('SELL', qty_to_trade)
        if is_pre_market() or is_post_market():
            bid_price = await get_current_price(symbol, is_ask=False)
            if bid_price <= 0:
                log.error(f"Invalid bid price for {symbol}")
                return response.json({"status": "error", "message": "Invalid price"})
            trade_order = create_order('SELL', qty_to_trade, bid_price)
            trade = ib.placeOrder(contract, trade_order)
            asyncio.create_task(monitor_and_resubmit_order(trade.order.orderId, symbol, 'SELL', datetime.now()))
        else:
            trade = ib.placeOrder(contract, trade_order)
        log.info(f"Executed SELL {qty_to_trade} {symbol}. Trade: {trade}")

    return response.json({"status": "success", "message": f"Signal processed for {symbol}"})

# IB Error Handler
def on_ib_error(reqId, errorCode, errorString, contract):
    log.error(f"IB Error {errorCode}: {errorString} for {contract}")

# Reconnect check
async def periodic_reconnect():
    global ib
    while True:
        await asyncio.sleep(60)
        if not ib.isConnected():
            log.info("Reconnecting to IB...")
            ib.connect(HOST, DEMO_PORT, clientId=1)
            ib.errorEvent += on_ib_error
            ib.orderStatusEvent += lambda *args: log.info(f"Order Status: {args}")
            log.info("Reconnected to IB")

async def main():
    global ib
    ib = IB()
    log.info("Connecting to IB...")
    ib.connect(HOST, DEMO_PORT, clientId=1)
    ib.errorEvent += on_ib_error
    ib.orderStatusEvent += lambda *args: log.info(f"Order Status: {args}")
    log.info("Successfully Connected to IB")

    asyncio.create_task(periodic_reconnect())
    app.run(port=5000)

if __name__ == '__main__':
    util.startLoop()  # Initialize IB async loop
    asyncio.run(main())