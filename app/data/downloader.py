from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from app.clients.binance_rest import BinanceRestClient
from app.config import get_settings
from app.data.models import normalize_klines, to_milliseconds
from app.data.store import save_klines
from app.utils.logger import logger


class KlineDownloader:
    def __init__(self, client: BinanceRestClient | None = None):
        self.settings = get_settings()
        self.client = client or BinanceRestClient()

    def fetch_range(
        self,
        symbol: str,
        interval: str,
        start_time_ms: int,
        end_time_ms: int,
    ) -> pd.DataFrame:
        all_klines: list[list] = []
        current_start = start_time_ms
        batch = 1

        while current_start < end_time_ms:
            klines = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=1000,
                start_time=current_start,
                end_time=end_time_ms,
            )
            if not klines:
                break

            all_klines.extend(klines)
            last_open_time = int(klines[-1][0])
            if last_open_time <= current_start:
                break

            current_start = last_open_time + 1
            logger.info(
                f"Kline batch={batch} fetched={len(klines)} last_open_time={last_open_time}"
            )
            batch += 1
            time.sleep(0.2)

        return normalize_klines(all_klines)

    def fetch_last_days(self, days: int | None = None) -> pd.DataFrame:
        days = days if days is not None else self.settings.history_days
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=days)
        return self.fetch_range(
            symbol=self.settings.symbol,
            interval=self.settings.interval,
            start_time_ms=to_milliseconds(start_dt),
            end_time_ms=to_milliseconds(end_dt),
        )

    def fetch_latest(self, bars: int) -> pd.DataFrame:
        klines = self.client.get_klines(
            symbol=self.settings.symbol,
            interval=self.settings.interval,
            limit=bars,
        )
        return normalize_klines(klines)

    def fetch_and_store_last_days(self, days: int | None = None) -> Path:
        df = self.fetch_last_days(days=days)
        filename = (
            f"{self.settings.symbol.lower()}_{self.settings.interval}_"
            f"last_{days or self.settings.history_days}d.parquet"
        )
        target = self.settings.kline_data_dir / filename
        return save_klines(df, target)


if __name__ == "__main__":
    downloader = KlineDownloader()
    saved = downloader.fetch_and_store_last_days()
    logger.info(f"Stored historical klines at {saved}")
