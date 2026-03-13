from __future__ import annotations

import logging
import sys
from pathlib import Path

from app.config import get_settings


settings = get_settings()
LOG_LEVEL = getattr(logging, settings.log_level.upper(), logging.INFO)



def _build_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)
    logger.propagate = False
    return logger



def _reset_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)



def _ensure_dirs() -> None:
    Path("logs").mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)



def _file_handler(path: str, level: int) -> logging.Handler:
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setLevel(level)
    return handler



def configure_logger() -> tuple[logging.Logger, logging.Logger]:
    _ensure_dirs()

    app_logger = _build_logger("binance_quant.app")
    trade_logger = _build_logger("binance_quant.trade")
    error_logger = _build_logger("binance_quant.error")

    for lg in (app_logger, trade_logger, error_logger):
        _reset_handlers(lg)

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(LOG_LEVEL)
    console.setFormatter(formatter)

    app_file = _file_handler("logs/app.log", LOG_LEVEL)
    app_file.setFormatter(formatter)

    app_file_data = _file_handler(str(settings.logs_dir / "app.log"), LOG_LEVEL)
    app_file_data.setFormatter(formatter)

    trade_file = _file_handler("logs/trade.log", logging.INFO)
    trade_file.setFormatter(formatter)

    trade_file_data = _file_handler(str(settings.logs_dir / "trade.log"), logging.INFO)
    trade_file_data.setFormatter(formatter)

    error_file = _file_handler("logs/error.log", logging.ERROR)
    error_file.setFormatter(formatter)

    error_file_data = _file_handler(str(settings.logs_dir / "error.log"), logging.ERROR)
    error_file_data.setFormatter(formatter)

    app_logger.addHandler(console)
    app_logger.addHandler(app_file)
    app_logger.addHandler(app_file_data)
    app_logger.addHandler(error_file)
    app_logger.addHandler(error_file_data)

    trade_logger.addHandler(console)
    trade_logger.addHandler(trade_file)
    trade_logger.addHandler(trade_file_data)

    error_logger.addHandler(console)
    error_logger.addHandler(error_file)
    error_logger.addHandler(error_file_data)

    return app_logger, trade_logger


logger, trade_logger = configure_logger()
