from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


TESTNET_REST_BASE_URL = "https://testnet.binance.vision"
PROD_REST_BASE_URL = "https://api.binance.com"
TESTNET_WS_BASE_URL = "wss://stream.testnet.binance.vision/ws"
PROD_WS_BASE_URL = "wss://stream.binance.com:9443/ws"



def _parse_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}



def _parse_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)



def _parse_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    return float(value)


@dataclass(frozen=True)
class Settings:
    env: str
    testnet: bool
    run_mode: str
    symbol: str
    interval: str

    api_key: str
    api_secret: str
    rest_base_url: str
    ws_base_url: str

    order_notional_usdt: float
    max_position_qty: float
    max_trades_per_minute: int
    max_daily_loss_usdt: float
    max_consecutive_losses: int

    strategy_short_window: int
    strategy_long_window: int

    taker_fee_rate: float
    maker_fee_rate: float

    history_days: int
    preload_bars: int

    data_dir: Path
    raw_data_dir: Path
    kline_data_dir: Path
    logs_dir: Path

    enable_trade_stream: bool
    enable_auto_trading: bool
    log_level: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    env = os.getenv("ENV", "testnet").strip().lower()
    testnet = _parse_bool("TESTNET", env != "prod")

    rest_base_url = os.getenv(
        "BINANCE_BASE_URL",
        TESTNET_REST_BASE_URL if testnet else PROD_REST_BASE_URL,
    )
    ws_base_url = os.getenv(
        "BINANCE_WS_BASE_URL",
        TESTNET_WS_BASE_URL if testnet else PROD_WS_BASE_URL,
    )

    root_data_dir = Path(os.getenv("DATA_DIR", "data"))
    raw_data_dir = root_data_dir / "raw"
    kline_data_dir = root_data_dir / "klines"
    logs_dir = root_data_dir / "logs"

    return Settings(
        env=env,
        testnet=testnet,
        run_mode=os.getenv("RUN_MODE", "backtest").strip().lower(),
        symbol=os.getenv("SYMBOL", "BTCUSDT").upper(),
        interval=os.getenv("KLINE_INTERVAL", "1s"),
        api_key=os.getenv("BINANCE_API_KEY", ""),
        api_secret=os.getenv("BINANCE_API_SECRET", ""),
        rest_base_url=rest_base_url,
        ws_base_url=ws_base_url,
        order_notional_usdt=_parse_float("ORDER_NOTIONAL_USDT", 50.0),
        max_position_qty=_parse_float("MAX_POSITION_QTY", 0.01),
        max_trades_per_minute=_parse_int("MAX_TRADES_PER_MINUTE", 1),
        max_daily_loss_usdt=_parse_float("MAX_DAILY_LOSS_USDT", 100.0),
        max_consecutive_losses=_parse_int("MAX_CONSECUTIVE_LOSSES", 3),
        strategy_short_window=_parse_int("MA_SHORT_WINDOW", 5),
        strategy_long_window=_parse_int("MA_LONG_WINDOW", 20),
        taker_fee_rate=_parse_float("TAKER_FEE_RATE", 0.001),
        maker_fee_rate=_parse_float("MAKER_FEE_RATE", 0.001),
        history_days=_parse_int("HISTORY_DAYS", 7),
        preload_bars=_parse_int("PRELOAD_BARS", 200),
        data_dir=root_data_dir,
        raw_data_dir=raw_data_dir,
        kline_data_dir=kline_data_dir,
        logs_dir=logs_dir,
        enable_trade_stream=_parse_bool("ENABLE_TRADE_STREAM", False),
        enable_auto_trading=_parse_bool("ENABLE_AUTO_TRADING", False),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )


# Backward compatibility constants for existing imports.
_SETTINGS = get_settings()
BINANCE_API_KEY = _SETTINGS.api_key
BINANCE_API_SECRET = _SETTINGS.api_secret
BINANCE_BASE_URL = _SETTINGS.rest_base_url
ENV = _SETTINGS.env
SYMBOL = _SETTINGS.symbol
