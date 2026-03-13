from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.backtest.metrics import summarize
from app.data.models import KlineBar, row_to_bar
from app.strategy.base import BaseStrategy, SignalType


@dataclass
class BacktestConfig:
    initial_cash: float = 1_000.0
    fee_rate: float = 0.001
    fill_mode: str = "next_open"


class BacktestEngine:
    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()

    def run(self, klines: pd.DataFrame, strategy: BaseStrategy) -> dict[str, Any]:
        if klines.empty:
            raise ValueError("Kline dataframe is empty")

        strategy.reset()

        cash = self.config.initial_cash
        position_qty = 0.0
        entry_value = 0.0

        equity_points: list[dict[str, float]] = []
        trades: list[dict[str, Any]] = []
        trade_pnls: list[float] = []

        bars = klines.reset_index(drop=True)
        last_idx = len(bars) - 1

        for idx in range(last_idx):
            row = bars.iloc[idx]
            bar: KlineBar = row_to_bar(row)
            signal = strategy.on_bar(bar)

            exec_price = self._execution_price(bars=bars, idx=idx)
            bar_time = int(row["close_time"])

            if signal.action == SignalType.BUY and position_qty <= 0 and cash > 0:
                buy_qty = cash / exec_price
                if buy_qty > 0:
                    cost = buy_qty * exec_price
                    fee = cost * self.config.fee_rate
                    cash -= cost + fee
                    position_qty = buy_qty
                    entry_value = cost + fee
                    trades.append(
                        {
                            "time": bar_time,
                            "side": "BUY",
                            "price": exec_price,
                            "qty": buy_qty,
                            "fee": fee,
                            "signal": signal.reason,
                        }
                    )

            elif signal.action == SignalType.SELL and position_qty > 0:
                proceed = position_qty * exec_price
                fee = proceed * self.config.fee_rate
                pnl = proceed - fee - entry_value
                cash += proceed - fee
                trade_pnls.append(pnl)
                trades.append(
                    {
                        "time": bar_time,
                        "side": "SELL",
                        "price": exec_price,
                        "qty": position_qty,
                        "fee": fee,
                        "pnl": pnl,
                        "signal": signal.reason,
                    }
                )
                position_qty = 0.0
                entry_value = 0.0

            mark_price = float(row["close"])
            equity = cash + position_qty * mark_price
            equity_points.append({"time": bar_time, "equity": equity})

        last_close = float(bars.iloc[last_idx]["close"])
        final_equity = cash + position_qty * last_close

        equity_df = pd.DataFrame(equity_points)
        equity_series = equity_df["equity"] if not equity_df.empty else pd.Series(dtype=float)
        summary = summarize(
            initial_cash=self.config.initial_cash,
            final_equity=final_equity,
            equity_curve=equity_series,
            trade_pnls=trade_pnls,
        )

        return {
            "summary": summary,
            "trades": pd.DataFrame(trades),
            "equity_curve": equity_df,
        }

    def _execution_price(self, bars: pd.DataFrame, idx: int) -> float:
        if self.config.fill_mode == "next_open" and idx + 1 < len(bars):
            return float(bars.iloc[idx + 1]["open"])
        return float(bars.iloc[idx]["close"])
