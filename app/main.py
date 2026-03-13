from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

from app.backtest.engine import BacktestConfig, BacktestEngine
from app.clients.binance_rest import BinanceRestClient
from app.clients.binance_ws import ReconnectingWebSocketClient, UserDataStreamClient
from app.config import get_settings
from app.data.downloader import KlineDownloader
from app.data.models import KlineBar, kline_message_to_bar, row_to_bar
from app.data.store import save_klines
from app.execution.orders import SymbolConstraints, parse_symbol_constraints
from app.execution.trader import SpotTrader
from app.portfolio.account_state import AccountState
from app.risk.position_sizer import FixedNotionalPositionSizer
from app.risk.rules import HardRiskRules
from app.strategy.base import SignalType
from app.strategy.ma_cross import MACrossStrategy
from app.utils.logger import logger, trade_logger


class TradingApp:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.rest = BinanceRestClient()
        self.downloader = KlineDownloader(client=self.rest)

        self.account_state = AccountState(symbol=self.settings.symbol)
        self.strategy = MACrossStrategy(
            short_window=self.settings.strategy_short_window,
            long_window=self.settings.strategy_long_window,
        )

        self.constraints: SymbolConstraints | None = None
        self.trader: SpotTrader | None = None

        self.market_ws: ReconnectingWebSocketClient | None = None
        self.user_ws: UserDataStreamClient | None = None

        self.bars: deque[KlineBar] = deque(maxlen=max(self.settings.preload_bars, 1000))
        self._stop_event = threading.Event()
        self._latest_price = 0.0

    def run(self) -> None:
        if self.settings.run_mode == "backtest":
            self.run_backtest()
            return

        self.run_live()

    def run_backtest(self) -> None:
        logger.info("Run mode: backtest")
        klines = self.downloader.fetch_last_days(days=self.settings.history_days)
        if klines.empty:
            raise RuntimeError("No historical kline data fetched for backtest")

        target = self.settings.kline_data_dir / (
            f"{self.settings.symbol.lower()}_{self.settings.interval}_last_{self.settings.history_days}d.parquet"
        )
        saved = save_klines(klines, target)
        logger.info(f"Backtest data saved to {saved}")

        strategy = MACrossStrategy(
            short_window=self.settings.strategy_short_window,
            long_window=self.settings.strategy_long_window,
        )
        engine = BacktestEngine(
            BacktestConfig(initial_cash=1_000.0, fee_rate=self.settings.taker_fee_rate, fill_mode="next_open")
        )
        result = engine.run(klines=klines, strategy=strategy)

        summary = result["summary"]
        logger.info(
            "Backtest summary: "
            f"return={summary['return']:.4%} "
            f"max_drawdown={summary['max_drawdown']:.4%} "
            f"win_rate={summary['win_rate']:.2%} "
            f"trade_count={int(summary['trade_count'])} "
            f"final_equity={summary['final_equity']:.2f} "
            f"sharpe={summary['sharpe']:.3f}"
        )

    def run_live(self) -> None:
        logger.info(f"Run mode: {self.settings.run_mode} symbol={self.settings.symbol}")
        if not self.settings.api_key or not self.settings.api_secret:
            raise RuntimeError("RUN_MODE=live requires BINANCE_API_KEY and BINANCE_API_SECRET")

        self._initialize_rest_and_symbol()
        self._sync_account_state()
        self._preload_history()
        self._initialize_trader()

        self._start_market_stream()
        self._start_user_stream()

        try:
            while not self._stop_event.is_set():
                self.account_state.ws_healthy = bool(
                    self.market_ws and self.market_ws.is_connected and self.user_ws and self.user_ws.is_connected
                )
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received, stopping app")
        finally:
            self.stop()

    def stop(self) -> None:
        self._stop_event.set()
        if self.market_ws:
            self.market_ws.stop()
        if self.user_ws:
            self.user_ws.stop()

    def _initialize_rest_and_symbol(self) -> None:
        server_time = self.rest.get_server_time()
        logger.info(f"Server time: {server_time}")

        exchange_info = self.rest.get_exchange_info(symbol=self.settings.symbol)
        timezone = exchange_info.get("timezone")
        logger.info(f"Exchange timezone: {timezone}")

        filters = self.rest.get_symbol_filters(self.settings.symbol)
        self.constraints = parse_symbol_constraints(filters)
        self._validate_symbol_constraints(self.constraints)

    def _validate_symbol_constraints(self, constraints: SymbolConstraints) -> None:
        if constraints.step_size <= 0:
            raise RuntimeError("Invalid symbol filter: step_size")
        if constraints.min_qty < 0:
            raise RuntimeError("Invalid symbol filter: min_qty")
        if constraints.min_notional < 0:
            raise RuntimeError("Invalid symbol filter: min_notional")

        logger.info(
            "Symbol constraints "
            f"min_qty={constraints.min_qty} step_size={constraints.step_size} "
            f"min_notional={constraints.min_notional} tick_size={constraints.tick_size}"
        )

    def _sync_account_state(self) -> None:
        account = self.rest.get_account()
        self.account_state.sync_from_account_payload(account)

        open_orders = self.rest.get_open_orders(symbol=self.settings.symbol)
        self.account_state.sync_open_orders(open_orders)

        logger.info(
            "Account synced "
            f"base_free={self.account_state.get_free_balance(self.account_state.base_asset):.8f} "
            f"quote_free={self.account_state.get_free_balance(self.account_state.quote_asset):.8f} "
            f"open_orders={len(self.account_state.open_orders)}"
        )

    def _preload_history(self) -> None:
        bars_needed = max(self.settings.preload_bars, self.settings.strategy_long_window + 5)
        df = self.downloader.fetch_latest(bars=bars_needed)
        if df.empty:
            raise RuntimeError("Failed to preload historical bars")

        for _, row in df.iterrows():
            bar = row_to_bar(row)
            self.bars.append(bar)
            self.strategy.on_bar(bar)

        self._latest_price = float(df.iloc[-1]["close"])
        logger.info(f"Preloaded bars={len(self.bars)} latest_price={self._latest_price}")

    def _initialize_trader(self) -> None:
        if not self.constraints:
            raise RuntimeError("Trader initialization requires symbol constraints")

        risk_rules = HardRiskRules(
            max_order_notional=self.settings.order_notional_usdt,
            max_position_qty=self.settings.max_position_qty,
            max_trades_per_minute=self.settings.max_trades_per_minute,
            max_daily_loss_usdt=self.settings.max_daily_loss_usdt,
            max_consecutive_losses=self.settings.max_consecutive_losses,
        )
        sizer = FixedNotionalPositionSizer(order_notional_usdt=self.settings.order_notional_usdt)

        self.trader = SpotTrader(
            settings=self.settings,
            rest_client=self.rest,
            account_state=self.account_state,
            risk_rules=risk_rules,
            sizer=sizer,
            constraints=self.constraints,
        )

    def _start_market_stream(self) -> None:
        streams = [f"{self.settings.symbol.lower()}@kline_{self.settings.interval}"]
        if self.settings.enable_trade_stream:
            streams.append(f"{self.settings.symbol.lower()}@trade")

        self.market_ws = ReconnectingWebSocketClient(
            url=self.settings.ws_base_url,
            name="market",
            on_message=self._on_market_message,
            subscriptions=streams,
        )
        self.market_ws.start()

    def _start_user_stream(self) -> None:
        self.user_ws = UserDataStreamClient(
            rest_client=self.rest,
            ws_base_url=self.settings.ws_base_url,
            on_message=self._on_user_message,
        )
        self.user_ws.start()

    def _on_market_message(self, message: dict[str, Any]) -> None:
        event_type = message.get("e")

        if event_type == "trade" and self.settings.enable_trade_stream:
            return

        if event_type != "kline":
            return

        kline = message.get("k", {})
        if kline.get("s") != self.settings.symbol:
            return
        if not bool(kline.get("x")):
            return

        bar = kline_message_to_bar(message)
        if not bar:
            return

        self.bars.append(bar)
        self._latest_price = bar.close

        signal = self.strategy.on_bar(bar)
        logger.info(
            f"Signal action={signal.action.value} reason={signal.reason} "
            f"price={bar.close} close_time={bar.close_time}"
        )

        if signal.action == SignalType.HOLD:
            return
        if not self.trader:
            return

        result = self.trader.handle_signal(signal=signal, last_price=bar.close)
        trade_logger.info(f"Trade decision signal={signal.action.value} result={result}")

    def _on_user_message(self, message: dict[str, Any]) -> None:
        self.account_state.update_from_user_stream(message)

        event_type = message.get("e", "unknown")
        logger.info(f"User stream event={event_type}")


if __name__ == "__main__":
    app = TradingApp()
    app.run()
