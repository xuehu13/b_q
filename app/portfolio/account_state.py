from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.portfolio.position_state import PositionState


COMMON_QUOTES = ["USDT", "FDUSD", "USDC", "BUSD", "BTC", "ETH", "BNB", "EUR", "TRY"]



def parse_symbol_assets(symbol: str) -> tuple[str, str]:
    symbol = symbol.upper()
    for quote in sorted(COMMON_QUOTES, key=len, reverse=True):
        if symbol.endswith(quote):
            return symbol[: -len(quote)], quote
    return symbol[:-4], symbol[-4:]


@dataclass
class AccountState:
    symbol: str
    base_asset: str = field(init=False)
    quote_asset: str = field(init=False)

    balances_free: dict[str, float] = field(default_factory=dict)
    balances_locked: dict[str, float] = field(default_factory=dict)
    open_orders: dict[str, dict[str, Any]] = field(default_factory=dict)
    position: PositionState = field(default_factory=PositionState)

    daily_realized_pnl: float = 0.0
    consecutive_losses: int = 0
    ws_healthy: bool = True
    account_healthy: bool = True

    trade_timestamps_ms: deque[int] = field(default_factory=deque)
    last_execution_events: list[dict[str, Any]] = field(default_factory=list)

    _current_day: datetime.date = field(default_factory=lambda: datetime.now(timezone.utc).date())

    def __post_init__(self) -> None:
        self.symbol = self.symbol.upper()
        self.base_asset, self.quote_asset = parse_symbol_assets(self.symbol)

    def sync_from_account_payload(self, account_payload: dict[str, Any]) -> None:
        balances = account_payload.get("balances", [])
        for balance in balances:
            asset = balance.get("asset")
            if not asset:
                continue
            self.balances_free[asset] = float(balance.get("free", 0.0))
            self.balances_locked[asset] = float(balance.get("locked", 0.0))

        base_total = self.balances_free.get(self.base_asset, 0.0) + self.balances_locked.get(
            self.base_asset, 0.0
        )
        self.position.quantity = base_total
        if base_total <= 1e-12:
            self.position.quantity = 0.0
            self.position.avg_price = 0.0

        self.account_healthy = True

    def sync_open_orders(self, open_orders: list[dict[str, Any]]) -> None:
        self.open_orders = {
            str(order.get("orderId") or order.get("clientOrderId")): order for order in open_orders
        }

    def add_pending_order(self, order_key: str, order_payload: dict[str, Any]) -> None:
        self.open_orders[order_key] = order_payload

    def remove_order(self, order_key: str) -> None:
        self.open_orders.pop(order_key, None)

    def get_free_balance(self, asset: str) -> float:
        return self.balances_free.get(asset, 0.0)

    def trades_last_minute(self, now_ms: int) -> int:
        self._prune_trade_timestamps(now_ms)
        return len(self.trade_timestamps_ms)

    def _prune_trade_timestamps(self, now_ms: int) -> None:
        threshold = now_ms - 60_000
        while self.trade_timestamps_ms and self.trade_timestamps_ms[0] < threshold:
            self.trade_timestamps_ms.popleft()

    def _roll_daily_pnl_if_needed(self) -> None:
        today = datetime.now(timezone.utc).date()
        if today != self._current_day:
            self._current_day = today
            self.daily_realized_pnl = 0.0

    def register_execution(self, side: str, quantity: float, price: float, fee: float = 0.0) -> None:
        self._roll_daily_pnl_if_needed()
        realized = self.position.on_fill(side=side, quantity=quantity, price=price, fee=fee)
        if realized != 0.0:
            self.daily_realized_pnl += realized
            if realized < 0:
                self.consecutive_losses += 1
            else:
                self.consecutive_losses = 0

    def mark_trade(self, event_time_ms: int, payload: dict[str, Any] | None = None) -> None:
        self.trade_timestamps_ms.append(event_time_ms)
        if payload:
            self.last_execution_events.append(payload)
            if len(self.last_execution_events) > 50:
                self.last_execution_events.pop(0)

    def update_from_user_stream(self, message: dict[str, Any]) -> None:
        event_type = message.get("e")

        if event_type == "outboundAccountPosition":
            for item in message.get("B", []):
                asset = item.get("a")
                if not asset:
                    continue
                self.balances_free[asset] = float(item.get("f", 0.0))
                self.balances_locked[asset] = float(item.get("l", 0.0))
            return

        if event_type != "executionReport":
            return

        order_id = str(message.get("i") or message.get("c"))
        order_status = message.get("X")
        side = message.get("S", "").upper()

        if order_status in {"NEW", "PARTIALLY_FILLED"}:
            self.open_orders[order_id] = message
        elif order_status in {"FILLED", "CANCELED", "EXPIRED", "REJECTED"}:
            self.open_orders.pop(order_id, None)

        last_qty = float(message.get("l", 0.0))
        last_price = float(message.get("L", 0.0))
        commission = float(message.get("n", 0.0)) if message.get("n") else 0.0
        event_time = int(message.get("E", 0))

        if last_qty > 0 and last_price > 0 and side in {"BUY", "SELL"}:
            self.register_execution(side=side, quantity=last_qty, price=last_price, fee=commission)
            if event_time > 0:
                self.mark_trade(event_time_ms=event_time, payload=message)

    @property
    def has_open_orders(self) -> bool:
        return bool(self.open_orders)
