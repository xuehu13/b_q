from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN



def _to_decimal(value: float | str) -> Decimal:
    return Decimal(str(value))



def floor_to_step(value: float, step: float) -> float:
    value_dec = _to_decimal(value)
    step_dec = _to_decimal(step)
    if step_dec <= 0:
        return float(value_dec)

    steps = (value_dec / step_dec).to_integral_value(rounding=ROUND_DOWN)
    return float(steps * step_dec)


@dataclass
class FixedNotionalPositionSizer:
    order_notional_usdt: float

    def size_for_buy(
        self,
        price: float,
        step_size: float,
        min_qty: float,
        min_notional: float,
        max_qty: float | None = None,
    ) -> float:
        if price <= 0:
            return 0.0

        raw_qty = self.order_notional_usdt / price
        qty = floor_to_step(raw_qty, step_size)

        if max_qty is not None and qty > max_qty:
            qty = floor_to_step(max_qty, step_size)

        if qty < min_qty:
            return 0.0

        if qty * price < min_notional:
            adjusted_qty = floor_to_step(min_notional / price, step_size)
            if adjusted_qty < min_qty:
                return 0.0
            qty = adjusted_qty

        return qty
