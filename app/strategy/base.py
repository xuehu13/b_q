from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from app.data.models import KlineBar


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class StrategySignal:
    action: SignalType
    reason: str
    bar_time: int


class BaseStrategy(ABC):
    name: str

    @abstractmethod
    def on_bar(self, bar: KlineBar) -> StrategySignal:
        raise NotImplementedError

    @abstractmethod
    def reset(self) -> None:
        raise NotImplementedError
