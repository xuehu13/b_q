from __future__ import annotations

import numpy as np
import pandas as pd



def compute_max_drawdown(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1.0
    return float(drawdown.min())



def compute_sharpe(returns: pd.Series, periods_per_year: int = 31_536_000) -> float:
    if returns.empty:
        return 0.0
    std = returns.std(ddof=0)
    if std == 0 or np.isnan(std):
        return 0.0
    return float((returns.mean() / std) * np.sqrt(periods_per_year))



def summarize(
    initial_cash: float,
    final_equity: float,
    equity_curve: pd.Series,
    trade_pnls: list[float],
) -> dict[str, float]:
    total_return = (final_equity - initial_cash) / initial_cash if initial_cash > 0 else 0.0
    win_trades = sum(1 for x in trade_pnls if x > 0)
    total_trades = len(trade_pnls)
    win_rate = (win_trades / total_trades) if total_trades else 0.0

    returns = equity_curve.pct_change().replace([np.inf, -np.inf], np.nan).dropna()

    return {
        "initial_cash": float(initial_cash),
        "final_equity": float(final_equity),
        "return": float(total_return),
        "max_drawdown": compute_max_drawdown(equity_curve),
        "win_rate": float(win_rate),
        "trade_count": float(total_trades),
        "sharpe": compute_sharpe(returns),
    }
