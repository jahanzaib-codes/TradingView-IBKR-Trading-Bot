# TradingView-IBKR-Trading-Bot

A Python-based automated trading bot that integrates TradingView alerts with Interactive Brokers (IBKR) to execute trades. This bot processes buy/sell signals from TradingView via webhooks and places orders on IBKR, supporting pre-market, regular, and post-market trading with sequence-based logic and limit order resubmission.

## Features

- **TradingView Integration**: Receives buy/sell signals via webhooks using the Alert Detector TTA Chrome extension (for free TradingView plans).
- **Sequence-Based Trading**: Closes opposite positions before opening new ones (e.g., close short before going long).
- **Market-Specific Orders**:
  - Pre-market (4:00–9:30 AM ET): Limit orders at ask price.
  - Regular hours (9:30 AM–4:00 PM ET): Market orders.
  - Post-market (4:00–8:00 PM ET): Limit orders at bid price.
- **Limit Order Resubmission**: Automatically resubmits unfilled limit orders after 3 minutes at current ask/bid price.
- **Flexible Contracts**: Supports any US stock (e.g., TSLA, AAPL) with default STK, SMART, USD settings.
- **Debugging & Logging**: Comprehensive logs for monitoring trades and errors.

## Prerequisites

- **Python 3.10+**: Ensure Python is installed.
- **IBKR TWS or Gateway**: Configured for API access (paper trading: port 7497, live: port 7496).
- **TradingView Account**: Free plan users require the [Alert Detector TTA Chrome extension](https://chrome.google.com/webstore/detail/alert-detector-tta).
- **Ngrok**: For exposing the local server to the internet ([Ngrok Documentation](https://ngrok.com/docs)).
- **Dependencies**:
  ```bash
  pip install ib_insync sanic pytz tzdata
  ```

## Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/jahanzaib-codes/TradingView-IBKR-Trading-Bot.git
cd TradingView-IBKR-Trading-Bot
```

### 2. Install Dependencies
```bash
pip install ib_insync sanic pytz tzdata
```

### 3. Configure IBKR TWS
- Open TWS (paper trading recommended for testing).
- Navigate to **File > Global Configuration > API > Settings**:
  - Enable "ActiveX and Socket Clients".
  - Set socket port to `7497` (paper) or `7496` (live).
  - Allow connections from `127.0.0.1` (localhost).
- Ensure an active market data subscription for pre/post-market trading.

### 4. Run the Bot
```bash
cd src
python app.py
```
- The server starts on `http://127.0.0.1:5000`.
- Check logs for IBKR connection status.

### 5. Set Up Ngrok
- Download and install Ngrok from [ngrok.com](https://ngrok.com).
- Run:
  ```bash
  ngrok http 5000
  ```
- Copy the Ngrok URL (e.g., `https://unintegrable-unredressed-rafael.ngrok-free.dev`).
- Webhook URL: `<ngrok-url>/webhook` (e.g., `https://unintegrable-unredressed-rafael.ngrok-free.dev/webhook`).

### 6. Configure TradingView Alerts
#### Step 1: Set Up Alert Detector TTA Extension
- Install the [Alert Detector TTA extension](https://chrome.google.com/webstore/detail/alert-detector-tta) from the Chrome Web Store.
- Open the extension settings (Chrome toolbar > Alert Detector TTA > Settings).
- Set the webhook URL: `https://<your-ngrok-url>.ngrok-free.dev/webhook`.
- Configure the payload:
  ```json
  {
    "action": "{{action}}",
    "symbol": "{{symbol}}"
  }
  ```
- For testing, use hardcoded values if placeholders fail:
  ```json
  {
    "action": "buy",
    "symbol": "TSLA"
  }
  ```

#### Step 2: Create TradingView Alert
- Open TradingView and load your strategy/indicator (e.g., for TSLA or AAPL).
- Click the Alert icon (clock) > Create Alert.
- Configure:
  - **Condition**: Select your strategy’s buy/sell signal.
  - **Options**: Set to "Once Per Bar" and no expiration (for testing).
  - **Message**: Use format: `action=buy,symbol=TSLA` or `action=sell,symbol=AAPL`.
- Save the alert.

#### Step 3: Test the Alert
- Trigger a dummy alert (e.g., price cross for TSLA).
- Check Ngrok dashboard (`http://127.0.0.1:4040`) for POST requests:
  ```json
  {
    "action": "buy",
    "symbol": "TSLA"
  }
  ```
- Verify app.py logs: `Executed BUY 1 TSLA`.
- Check TWS Trades tab for order execution.

## How It Works

- **Webhook**: Listens for POST requests at `/webhook` with JSON payload: `{"action": "buy", "symbol": "TSLA"}`.
- **Sequence Logic**:
  - Buy signal: Closes short positions, then opens a long position.
  - Sell signal: Closes long positions, then opens a short position.
  - Default position size: 1 share (configurable).
- **Order Types**:
  - Pre-market (4:00–9:30 AM ET): Limit order at ask price.
  - Regular hours (9:30 AM–4:00 PM ET): Market order.
  - Post-market (4:00–8:00 PM ET): Limit order at bid price.
- **Limit Order Resubmission**: Resubmits unfilled limit orders after 3 minutes at current ask/bid price.
- **Contracts**: Automatically creates stock contracts (STK, SMART, USD) for any US stock.

## Troubleshooting

1. **Timezone Error**
   - **Error**: `ModuleNotFoundError: No module named 'tzdata'`
   - **Fix**:
     ```bash
     pip install tzdata
     ```
     Verify:
     ```python
     import pytz
     print(pytz.timezone('US/Eastern'))
     ```

2. **Invalid Action**
   - **Error**: `Invalid action: ACTION`
   - **Cause**: Extension not parsing `{{action}}` or incorrect TradingView alert message.
   - **Fix**:
     - Ensure alert message: `action=buy,symbol=TSLA`.
     - Verify extension payload:
       ```json
       {
         "action": "{{action}}",
         "symbol": "{{symbol}}"
       }
       ```
     - Test with hardcoded payload:
       ```json
       {
         "action": "buy",
         "symbol": "TSLA"
       }
       ```

3. **No Trades in TWS**
   - **Checks**:
     - Verify TWS API settings (port 7497, localhost allowed).
     - Check TWS API logs (Global Configuration > API > View API Message Log).
     - Ensure market data subscription is active.
     - Check app.py logs for errors (e.g., `Invalid price`).
   - **Fix**:
     ```bash
     python app.py --debug
     ```
     Test with dummy alert: `action=buy,symbol=TSLA`.

4. **Ngrok Issues**
   - **Error**: Webhook not receiving requests.
   - **Fix**:
     - Ensure Ngrok is running: `ngrok http 5000`.
     - Check Ngrok dashboard (`http://127.0.0.1:4040`) for requests.
     - Update webhook URL in extension if Ngrok URL changes.

5. **Other Errors**
   - **IB Connection Failed**: Ensure TWS is open and API port is correct (7497 for paper).
   - **Invalid Symbol**: Use valid symbols (e.g., `TSLA`, not `{{TSLA}}`).
   - **Logs**: Check app.py logs and Ngrok dashboard for details.

## Customization

- **Change Quantity**: Modify `POSITION_SIZE` in `app.py`.
- **Add Stop-Loss/Take-Profit**: Update `create_order` in `app.py` to include stop/loss orders.
- **Live Trading**: Change `DEMO_PORT` to `LIVE_PORT` (7496) in `app.py`.

## Safety Notes

- Start with paper trading (port 7497) to avoid financial losses.
- Test thoroughly with dummy alerts before live trading.
- Monitor logs and TWS trades to ensure correct execution.

## Resources

- [Alert Detector TTA Setup](https://tradingview.to)
- [TradingView Free Plan Automation](https://www.tradingview.com/support/)
- [Ngrok Documentation](https://ngrok.com/docs)
- [IBKR API Guide](https://interactivebrokers.github.io/tws-api/)

## About the Author

Jahanzaib Ali is a Software Engineer and Blockchain Developer from Sukkur, Sindh, Pakistan. Specializing in AI-powered apps, blockchain wallets, and automated trading bots, Jahanzaib builds scalable, high-performance applications for web and mobile platforms.

- **GitHub**: [jahanzaib-codes](https://github.com/jahanzaib-codes)
- **LinkedIn**: [Jahanzaib Ali](https://linkedin.com/in/jahanzaib-ali)
- **Email**: Contact via GitHub

## License

This project is licensed under the MIT License.
