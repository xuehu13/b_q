from __future__ import annotations

import time
from typing import Any

from app.clients.binance_rest import BinanceRestClient
from app.config import Settings
from app.execution.orders import SymbolConstraints, build_client_order_id, normalize_quantity
from app.portfolio.account_state import AccountState
from app.risk.position_sizer import FixedNotionalPositionSizer
from app.risk.rules import HardRiskRules, RiskContext
from app.strategy.base import SignalType, StrategySignal
from app.utils.logger import logger, trade_logger


class SpotTrader:
    def __init__(
        self,
        settings: Settings,
        rest_client: BinanceRestClient,
        account_state: AccountState,
        risk_rules: HardRiskRules,
        sizer: FixedNotionalPositionSizer,
        constraints: SymbolConstraints,
    ):
        self.settings = settings
        self.rest_client = rest_client
        self.account_state = account_state
        self.risk_rules = risk_rules
        self.sizer = sizer
        self.constraints = constraints

    def handle_signal(self, signal: StrategySignal, last_price: float) -> dict[str, Any]:
        if signal.action == SignalType.HOLD:
            return {"status": "skip", "reason": "hold"}

        side = self._resolve_side(signal.action)
        if side is None:
            return {"status": "skip", "reason": "position_state_not_match"}

        quantity = self._compute_order_quantity(side=side, last_price=last_price)
        if quantity <= 0:
            return {"status": "skip", "reason": "quantity_too_small"}

        now_ms = int(time.time() * 1000)
        context = RiskContext(
            side=side,
            timestamp_ms=now_ms,
            price=last_price,
            quantity=quantity,
            notional=quantity * last_price,
            has_open_order=self.account_state.has_open_orders,
            current_position_qty=self.account_state.position.quantity,
            trades_last_minute=self.account_state.trades_last_minute(now_ms),
            daily_realized_pnl=self.account_state.daily_realized_pnl,
            consecutive_losses=self.account_state.consecutive_losses,
            ws_healthy=self.account_state.ws_healthy,
            account_healthy=self.account_state.account_healthy,
        )

        allowed, reason = self.risk_rules.can_trade(context)
        if not allowed:
            logger.warning(f"Risk blocked trade side={side} reason={reason}")
            return {"status": "blocked", "reason": reason}

        client_order_id = build_client_order_id(prefix="mvp")
        payload = {
            "symbol": self.settings.symbol,
            "side": side,
            "type": "MARKET",
            "quantity": quantity,
            "newClientOrderId": client_order_id,
        }

        trade_logger.info(f"Submit order payload={payload}")

        if not self.settings.enable_auto_trading:
            self.account_state.mark_trade(now_ms, payload={"paper_order": payload})
            return {
                "status": "paper_submitted",
                "reason": "ENABLE_AUTO_TRADING=false",
                "payload": payload,
            }

        try:
            response = self.rest_client.place_order(
                symbol=self.settings.symbol,
                side=side,
                order_type="MARKET",
                quantity=quantity,
                new_client_order_id=client_order_id,
            )
            order_key = str(response.get("orderId", client_order_id))
            self.account_state.add_pending_order(order_key=order_key, order_payload=response)
            trade_logger.info(f"Order submitted order_id={order_key} response={response}")
            return {"status": "submitted", "response": response}
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"Order submission failed error={exc}")
            return {"status": "error", "reason": str(exc)}

    def _resolve_side(self, action: SignalType) -> str | None:
        position_qty = self.account_state.position.quantity

        if action == SignalType.BUY:
            if position_qty > 0:
                return None
            return "BUY"

        if action == SignalType.SELL:
            if position_qty <= 0:
                return None
            return "SELL"

        return None

    def _compute_order_quantity(self, side: str, last_price: float) -> float:
        if side == "BUY":
            qty = self.sizer.size_for_buy(
                price=last_price,
                step_size=self.constraints.step_size,
                min_qty=self.constraints.min_qty,
                min_notional=self.constraints.min_notional,
                max_qty=self.constraints.max_qty,
            )
            return normalize_quantity(qty, self.constraints.step_size)

        if side == "SELL":
            qty = normalize_quantity(self.account_state.position.quantity, self.constraints.step_size)
            if qty < self.constraints.min_qty:
                return 0.0
            return qty

        return 0.0
