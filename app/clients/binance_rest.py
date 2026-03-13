from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

import requests

from app.config import get_settings


class BinanceRestClient:
    def __init__(self, base_url: str | None = None):
        self.settings = get_settings()
        self.base_url = (base_url or self.settings.rest_base_url).rstrip("/")
        self.api_key = self.settings.api_key
        self.api_secret = self.settings.api_secret
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"X-MBX-APIKEY": self.api_key})

    def _sign(self, params: dict[str, Any]) -> str:
        query = urlencode(params, doseq=True)
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        signed: bool = False,
    ) -> Any:
        params = params.copy() if params else {}

        if signed:
            if not self.api_key or not self.api_secret:
                raise RuntimeError("Signed request requires BINANCE_API_KEY and BINANCE_API_SECRET")
            params["timestamp"] = int(time.time() * 1000)
            params.setdefault("recvWindow", 5000)
            params["signature"] = self._sign(params)

        url = f"{self.base_url}{path}"
        response = self.session.request(method=method, url=url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    def get_server_time(self) -> dict[str, Any]:
        return self._request("GET", "/api/v3/time")

    def get_exchange_info(self, symbol: str | None = None) -> dict[str, Any]:
        params = {"symbol": symbol} if symbol else None
        return self._request("GET", "/api/v3/exchangeInfo", params=params)

    def get_symbol_info(self, symbol: str) -> dict[str, Any]:
        info = self.get_exchange_info(symbol=symbol)
        symbols = info.get("symbols", [])
        if not symbols:
            raise RuntimeError(f"Symbol not found in exchangeInfo: {symbol}")
        return symbols[0]

    def get_symbol_filters(self, symbol: str) -> dict[str, dict[str, Any]]:
        symbol_info = self.get_symbol_info(symbol)
        filters = symbol_info.get("filters", [])
        return {f["filterType"]: f for f in filters}

    def get_klines(
        self,
        symbol: str,
        interval: str = "1s",
        limit: int = 1000,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[list[Any]]:
        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        return self._request("GET", "/api/v3/klines", params=params)

    def get_account(self) -> dict[str, Any]:
        return self._request("GET", "/api/v3/account", signed=True)

    def get_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        params = {"symbol": symbol} if symbol else None
        return self._request("GET", "/api/v3/openOrders", params=params, signed=True)

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str = "MARKET",
        quantity: float | None = None,
        quote_order_qty: float | None = None,
        time_in_force: str | None = None,
        price: float | None = None,
        new_client_order_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
        }
        if quantity is not None:
            params["quantity"] = self._format_float(quantity)
        if quote_order_qty is not None:
            params["quoteOrderQty"] = self._format_float(quote_order_qty)
        if time_in_force:
            params["timeInForce"] = time_in_force
        if price is not None:
            params["price"] = self._format_float(price)
        if new_client_order_id:
            params["newClientOrderId"] = new_client_order_id

        return self._request("POST", "/api/v3/order", params=params, signed=True)

    def get_order(
        self,
        symbol: str,
        order_id: int | None = None,
        orig_client_order_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"symbol": symbol}
        if order_id is not None:
            params["orderId"] = order_id
        if orig_client_order_id is not None:
            params["origClientOrderId"] = orig_client_order_id
        return self._request("GET", "/api/v3/order", params=params, signed=True)

    def cancel_order(
        self,
        symbol: str,
        order_id: int | None = None,
        orig_client_order_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"symbol": symbol}
        if order_id is not None:
            params["orderId"] = order_id
        if orig_client_order_id is not None:
            params["origClientOrderId"] = orig_client_order_id
        return self._request("DELETE", "/api/v3/order", params=params, signed=True)

    def start_user_data_stream(self) -> str:
        payload = self._request("POST", "/api/v3/userDataStream")
        listen_key = payload.get("listenKey")
        if not listen_key:
            raise RuntimeError("Failed to get listenKey from userDataStream")
        return listen_key

    def keepalive_user_data_stream(self, listen_key: str) -> dict[str, Any]:
        return self._request("PUT", "/api/v3/userDataStream", params={"listenKey": listen_key})

    def close_user_data_stream(self, listen_key: str) -> dict[str, Any]:
        return self._request("DELETE", "/api/v3/userDataStream", params={"listenKey": listen_key})

    @staticmethod
    def _format_float(value: float) -> str:
        return f"{value:.12f}".rstrip("0").rstrip(".")
