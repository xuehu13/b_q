from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN


@dataclass(frozen=True)
class SymbolConstraints:
    min_qty: float
    max_qty: float
    step_size: float
    min_notional: float
    tick_size: float



def _d(value: float | str) -> Decimal:
    return Decimal(str(value))



def floor_by_step(value: float, step: float) -> float:
    value_dec = _d(value)
    step_dec = _d(step)
    if step_dec <= 0:
        return float(value_dec)
    steps = (value_dec / step_dec).to_integral_value(rounding=ROUND_DOWN)
    return float(steps * step_dec)



def normalize_price(price: float, tick_size: float) -> float:
    return floor_by_step(price, tick_size)



def normalize_quantity(quantity: float, step_size: float) -> float:
    return floor_by_step(quantity, step_size)



def parse_symbol_constraints(filters: dict[str, dict]) -> SymbolConstraints:
    lot = filters.get("LOT_SIZE", {})
    market_lot = filters.get("MARKET_LOT_SIZE", {})
    min_notional_filter = filters.get("MIN_NOTIONAL", {}) or filters.get("NOTIONAL", {})
    price_filter = filters.get("PRICE_FILTER", {})

    min_qty = float(lot.get("minQty", 0.0))
    max_qty = float(lot.get("maxQty", 0.0))
    step_size = float(lot.get("stepSize", 0.0))

    if market_lot:
        min_qty = max(min_qty, float(market_lot.get("minQty", 0.0)))
        max_qty = min(max_qty, float(market_lot.get("maxQty", max_qty))) if max_qty > 0 else float(
            market_lot.get("maxQty", 0.0)
        )
        market_step = float(market_lot.get("stepSize", 0.0))
        if market_step > 0:
            step_size = market_step

    return SymbolConstraints(
        min_qty=min_qty,
        max_qty=max_qty,
        step_size=step_size,
        min_notional=float(min_notional_filter.get("minNotional", 0.0)),
        tick_size=float(price_filter.get("tickSize", 0.0)),
    )



def build_client_order_id(prefix: str = "mvp") -> str:
    return f"{prefix}_{int(time.time() * 1000)}"
