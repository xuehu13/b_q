from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.utils.logger import logger



def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)



def save_klines(df: pd.DataFrame, path: Path) -> Path:
    ensure_parent(path)
    try:
        df.to_parquet(path, index=False)
        logger.info(f"Saved klines parquet to {path}")
        return path
    except Exception as exc:  # noqa: BLE001
        fallback = path.with_suffix(".csv")
        df.to_csv(fallback, index=False, encoding="utf-8-sig")
        logger.warning(
            "Parquet save failed, fell back to CSV. "
            f"target={path} fallback={fallback} error={exc}"
        )
        return fallback



def load_klines(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)
