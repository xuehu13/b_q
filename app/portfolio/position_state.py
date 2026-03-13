from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PositionState:
    quantity: float = 0.0
    avg_price: float = 0.0
    realized_pnl: float = 0.0

    def on_fill(self, side: str, quantity: float, price: float, fee: float = 0.0) -> float:
        if quantity <= 0:
            return 0.0

        side = side.upper()

        if side == "BUY":
            total_cost = self.avg_price * self.quantity + price * quantity + fee
            self.quantity += quantity
            if self.quantity > 0:
                self.avg_price = total_cost / self.quantity
            return 0.0

        if side == "SELL":
            sell_qty = min(quantity, self.quantity)
            if sell_qty <= 0:
                return 0.0

            pnl = (price - self.avg_price) * sell_qty - fee
            self.realized_pnl += pnl
            self.quantity -= sell_qty

            if self.quantity <= 1e-12:
                self.quantity = 0.0
                self.avg_price = 0.0

            return pnl

        raise ValueError(f"Unsupported side: {side}")
