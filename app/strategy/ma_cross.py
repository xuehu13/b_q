from __future__ import annotations

from collections import deque

from app.data.models import KlineBar
from app.strategy.base import BaseStrategy, SignalType, StrategySignal


class MACrossStrategy(BaseStrategy):
    name = "ma_cross"

    def __init__(self, short_window: int, long_window: int):
        if short_window <= 0 or long_window <= 0:
            raise ValueError("MA windows must be positive")
        if short_window >= long_window:
            raise ValueError("short_window must be smaller than long_window")

        self.short_window = short_window
        self.long_window = long_window
        self._closes: deque[float] = deque(maxlen=long_window)
        self._state = "neutral"

    def reset(self) -> None:
        self._closes.clear()
        self._state = "neutral"

    def on_bar(self, bar: KlineBar) -> StrategySignal:
        self._closes.append(bar.close)

        if len(self._closes) < self.long_window:
            return StrategySignal(
                action=SignalType.HOLD,
                reason="warmup",
                bar_time=bar.close_time,
            )

        short_ma = sum(list(self._closes)[-self.short_window :]) / self.short_window
        long_ma = sum(self._closes) / self.long_window

        if short_ma > long_ma and self._state != "long":
            self._state = "long"
            return StrategySignal(
                action=SignalType.BUY,
                reason=f"short_ma={short_ma:.4f} > long_ma={long_ma:.4f}",
                bar_time=bar.close_time,
            )

        if short_ma < long_ma and self._state != "flat":
            self._state = "flat"
            return StrategySignal(
                action=SignalType.SELL,
                reason=f"short_ma={short_ma:.4f} < long_ma={long_ma:.4f}",
                bar_time=bar.close_time,
            )

        return StrategySignal(
            action=SignalType.HOLD,
            reason=f"no_cross short_ma={short_ma:.4f} long_ma={long_ma:.4f}",
            bar_time=bar.close_time,
        )
