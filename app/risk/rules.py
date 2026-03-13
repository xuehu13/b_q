from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskContext:
    side: str
    timestamp_ms: int
    price: float
    quantity: float
    notional: float
    has_open_order: bool
    current_position_qty: float
    trades_last_minute: int
    daily_realized_pnl: float
    consecutive_losses: int
    ws_healthy: bool
    account_healthy: bool


class HardRiskRules:
    def __init__(
        self,
        max_order_notional: float,
        max_position_qty: float,
        max_trades_per_minute: int,
        max_daily_loss_usdt: float,
        max_consecutive_losses: int,
    ):
        self.max_order_notional = max_order_notional
        self.max_position_qty = max_position_qty
        self.max_trades_per_minute = max_trades_per_minute
        self.max_daily_loss_usdt = max_daily_loss_usdt
        self.max_consecutive_losses = max_consecutive_losses

    def can_trade(self, context: RiskContext) -> tuple[bool, str]:
        if not context.ws_healthy:
            return False, "ws_unhealthy"

        if not context.account_healthy:
            return False, "account_unhealthy"

        if context.has_open_order:
            return False, "open_order_exists"

        if context.quantity <= 0 or context.price <= 0:
            return False, "invalid_order_values"

        if context.side == "BUY" and context.notional > self.max_order_notional + 1e-8:
            return False, "single_order_notional_exceeded"

        if context.side == "BUY" and context.current_position_qty + context.quantity > self.max_position_qty + 1e-12:
            return False, "max_position_exceeded"

        if context.trades_last_minute >= self.max_trades_per_minute:
            return False, "trade_frequency_limited"

        if context.daily_realized_pnl <= -abs(self.max_daily_loss_usdt):
            return False, "daily_loss_limit_hit"

        if context.consecutive_losses >= self.max_consecutive_losses:
            return False, "consecutive_loss_limit_hit"

        return True, "ok"
