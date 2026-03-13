from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd


KLINE_COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "ignore",
]


@dataclass(frozen=True)
class KlineBar:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int

    @property
    def open_dt(self) -> datetime:
        return datetime.fromtimestamp(self.open_time / 1000, tz=timezone.utc)

    @property
    def close_dt(self) -> datetime:
        return datetime.fromtimestamp(self.close_time / 1000, tz=timezone.utc)



def to_milliseconds(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)



def normalize_klines(klines: list[list[Any]]) -> pd.DataFrame:
    df = pd.DataFrame(klines, columns=KLINE_COLUMNS)
    if df.empty:
        return df

    numeric_cols = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    int_cols = ["open_time", "close_time", "trade_count"]
    for col in int_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    df = df.dropna(subset=["open_time", "open", "high", "low", "close"])
    df["open_time"] = df["open_time"].astype(int)
    df["close_time"] = df["close_time"].astype(int)
    df["trade_count"] = df["trade_count"].fillna(0).astype(int)

    df["open_datetime"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_datetime"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    df = df.drop_duplicates(subset=["open_time"]).sort_values("open_time").reset_index(drop=True)
    return df



def row_to_bar(row: pd.Series) -> KlineBar:
    return KlineBar(
        open_time=int(row["open_time"]),
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        volume=float(row["volume"]),
        close_time=int(row["close_time"]),
    )



def kline_message_to_bar(message: dict[str, Any]) -> KlineBar | None:
    kline = message.get("k")
    if not kline:
        return None

    return KlineBar(
        open_time=int(kline["t"]),
        open=float(kline["o"]),
        high=float(kline["h"]),
        low=float(kline["l"]),
        close=float(kline["c"]),
        volume=float(kline["v"]),
        close_time=int(kline["T"]),
    )
