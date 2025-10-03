from ib_insync import Contract
from logger import LOGGER as log

def get_stock_contract(ticker: str) -> Contract:
    """
    Automatic contract for any US stock.
    """
    contract = Contract()
    contract.symbol = ticker.upper()
    contract.secType = "STK"  # Default stock
    contract.currency = "USD"
    contract.exchange = "SMART"  # Automatic routing
    log.info(f"Created contract for {ticker}: STK, SMART, USD")
    return contract