from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable

import websocket

from app.clients.binance_rest import BinanceRestClient
from app.utils.logger import logger

MessageHandler = Callable[[dict[str, Any]], None]


class ReconnectingWebSocketClient:
    def __init__(
        self,
        url: str,
        name: str,
        on_message: MessageHandler,
        subscriptions: list[str] | None = None,
        reconnect_delay_sec: float = 2.0,
    ):
        self.url = url
        self.name = name
        self.on_message = on_message
        self.subscriptions = subscriptions or []
        self.reconnect_delay_sec = reconnect_delay_sec

        self._ws_app: websocket.WebSocketApp | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._connected_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name=f"ws-{self.name}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._ws_app and self._ws_app.sock and self._ws_app.sock.connected:
            self._ws_app.close()
        if self._thread:
            self._thread.join(timeout=5)

    @property
    def is_connected(self) -> bool:
        return self._connected_event.is_set()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            logger.info(f"WS connect name={self.name} url={self.url}")
            self._ws_app = websocket.WebSocketApp(
                self.url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_ping=self._on_ping,
            )
            try:
                self._ws_app.run_forever(ping_interval=15, ping_timeout=10)
            except Exception as exc:  # noqa: BLE001
                logger.exception(f"WS run error name={self.name} error={exc}")

            self._connected_event.clear()
            if self._stop_event.is_set():
                break
            logger.warning(f"WS disconnected name={self.name}, reconnect in {self.reconnect_delay_sec}s")
            time.sleep(self.reconnect_delay_sec)

    def _on_open(self, ws: websocket.WebSocketApp) -> None:  # noqa: ARG002
        self._connected_event.set()
        logger.info(f"WS opened name={self.name}")
        if self.subscriptions:
            self.subscribe(self.subscriptions)

    def _on_message(self, ws: websocket.WebSocketApp, message: str) -> None:  # noqa: ARG002
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            logger.warning(f"WS non-json message name={self.name} message={message[:120]}")
            return

        if isinstance(payload, dict) and payload.get("result") is None and payload.get("id") is not None:
            return

        if isinstance(payload, dict) and "data" in payload:
            payload = payload["data"]

        self.on_message(payload)

    def _on_error(self, ws: websocket.WebSocketApp, error: Exception) -> None:  # noqa: ARG002
        logger.error(f"WS error name={self.name} error={error}")

    def _on_close(
        self,
        ws: websocket.WebSocketApp,  # noqa: ARG002
        close_status_code: int,
        close_msg: str,
    ) -> None:
        logger.warning(
            f"WS close name={self.name} status={close_status_code} reason={close_msg}"
        )

    def _on_ping(self, ws: websocket.WebSocketApp, message: bytes) -> None:
        try:
            ws.send(message, opcode=websocket.ABNF.OPCODE_PONG)
            logger.debug(f"WS pong sent name={self.name}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"WS pong failed name={self.name} error={exc}")

    def subscribe(self, streams: list[str]) -> None:
        if not streams:
            return
        if not self._ws_app:
            return

        payload = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": int(time.time()),
        }
        try:
            self._ws_app.send(json.dumps(payload))
            logger.info(f"WS subscribed name={self.name} streams={streams}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"WS subscribe failed name={self.name} error={exc}")


class UserDataStreamClient:
    def __init__(
        self,
        rest_client: BinanceRestClient,
        ws_base_url: str,
        on_message: MessageHandler,
    ):
        self.rest_client = rest_client
        self.ws_base_url = ws_base_url.rstrip("/")
        self.on_message = on_message

        self.listen_key: str | None = None
        self.ws_client: ReconnectingWebSocketClient | None = None
        self._keepalive_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        self.listen_key = self.rest_client.start_user_data_stream()
        url = f"{self.ws_base_url}/{self.listen_key}"
        self.ws_client = ReconnectingWebSocketClient(
            url=url,
            name="user-data",
            on_message=self.on_message,
            subscriptions=[],
        )
        self.ws_client.start()

        self._stop_event.clear()
        self._keepalive_thread = threading.Thread(
            target=self._keepalive_loop,
            name="user-data-keepalive",
            daemon=True,
        )
        self._keepalive_thread.start()
        logger.info("User data stream started")

    def stop(self) -> None:
        self._stop_event.set()
        if self.ws_client:
            self.ws_client.stop()

        if self.listen_key:
            try:
                self.rest_client.close_user_data_stream(self.listen_key)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"User data stream close failed error={exc}")

        if self._keepalive_thread:
            self._keepalive_thread.join(timeout=5)

    @property
    def is_connected(self) -> bool:
        return bool(self.ws_client and self.ws_client.is_connected)

    def _keepalive_loop(self) -> None:
        while not self._stop_event.is_set():
            if self._stop_event.wait(timeout=30 * 60):
                break
            if not self.listen_key:
                continue
            try:
                self.rest_client.keepalive_user_data_stream(self.listen_key)
                logger.info("User data stream keepalive sent")
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"User data keepalive failed error={exc}")
