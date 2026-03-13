
# Binance Quant MVP (Spot BTCUSDT)

## MVP Scope
- Market: Spot
- Symbol: `BTCUSDT`
- Data: `1s` kline (optional trade stream)
- Strategy: MA cross (`BUY` / `SELL` / `HOLD`)
- Execution: market order
- Environment: Spot Testnet first

## Structure
- `app/config.py`: central settings
- `app/clients/binance_rest.py`: REST API + signed endpoints
- `app/clients/binance_ws.py`: market/user websocket with reconnect
- `app/data/`: kline models, downloader, storage
- `app/strategy/`: strategy interface + MA cross
- `app/risk/`: position sizing + hard risk rules
- `app/portfolio/`: account/position state
- `app/execution/`: symbol filters + trader execution
- `app/backtest/`: engine + metrics
- `app/main.py`: app bootstrap and run loop

## Run Modes
- Backtest (default):
```powershell
$env:RUN_MODE="backtest"
python app/main.py
```

- Live/Testnet (paper order by default):
```powershell
$env:RUN_MODE="live"
$env:TESTNET="true"
$env:ENABLE_AUTO_TRADING="false"
python app/main.py
```

- Live/Testnet real order:
```powershell
$env:RUN_MODE="live"
$env:TESTNET="true"
$env:ENABLE_AUTO_TRADING="true"
python app/main.py
```

## Required .env Keys
- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`

## Important Configs
- `SYMBOL` (default `BTCUSDT`)
- `KLINE_INTERVAL` (default `1s`)
- `MA_SHORT_WINDOW` / `MA_LONG_WINDOW`
- `ORDER_NOTIONAL_USDT`
- `MAX_POSITION_QTY`
- `MAX_TRADES_PER_MINUTE`
- `MAX_DAILY_LOSS_USDT`
- `MAX_CONSECUTIVE_LOSSES`
- `ENABLE_TRADE_STREAM` (`true/false`)
- `ENABLE_AUTO_TRADING` (`true/false`)

## Logs
- `logs/app.log`
- `logs/trade.log`
- `logs/error.log`
- `data/logs/*.log`

