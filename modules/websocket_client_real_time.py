"""
modules/websocket_client_real_time.py
-------------------------------------
WebSocket client that:
- Subscribes to kbar & depth streams
- Prefills OHLCV via REST
- Keeps internal df_store & order_books
- Forwards ONLY ticker.* messages to core.message_handler via callback
- Handles reconnects, heartbeats, graceful shutdown
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict, deque
from typing import Any, Callable, Dict, Optional

import pandas as pd
import websockets

from utils.utils import fetch_initial_kline
from modules.indicator import IndicatorCalculator

# Optional helper to unify timeframe keys; if you don't have this file,
# either create it or inline a minimal normalize_tf.
try:
    from utils.timeframe import normalize_tf
except ImportError:  # fallback
    def normalize_tf(tf: str) -> str:
        t = tf.lower()
        aliases = {
            "1m": ["1m", "1min", "minute1"],
            "5m": ["5m", "5min", "minute5"],
            "15m": ["15m", "15min", "minute15"],
            "30m": ["30m", "30min", "minute30"],
            "1h": ["1h", "h1", "hour1"],
            "4h": ["4h", "h4", "hour4"],
            "8h": ["8h", "hour8"],
            "12h": ["12h", "hour12"],
            "1d": ["1d", "day1"],
            "1w": ["1w", "week1"],
            "1mth": ["1mth", "month1"],
        }
        for canon, alts in aliases.items():
            if t in alts:
                return canon
        return t


class WebSocketClient:
    def __init__(
        self,
        config: Dict[str, Any],
        logger: Optional[logging.Logger] = None,
        message_callback: Optional[Callable[..., asyncio.Future]] = None,
        trader: Any = None,
        strategy: Any = None,
        data_provider: Any = None,
    ):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self._message_callback = message_callback

        # URL
        self.url = (
            config.get("LBANK_API", {}).get("websocket_url")
            or config.get("WEBSOCKET_URL")
            or "wss://www.lbkex.net/ws/V2/"
        )
        self._ws_url = self.url  # some legacy code may still use this attr

        # Timeframe maps
        self.timeframe_mapping = (
            config.get("TIMEFRAME_MAPPING")
            or config.get("WEBSOCKET_TIMEFRAME_CODES", {})
            or {}
        )
        self.rest_code_map = (
            config.get("rest_code_map")
            or config.get("REST_TIMEFRAME_CODES")
            or {}
        )

        # Symbols / TFs
        self.symbols = (
            config.get("symbols")
            or config.get("SYMBOLS")
            or []
        )
        self.timeframes = (
            config.get("timeframes")
            or config.get("TIMEFRAMES")
            or []
        )

        # Optional deps
        self.trader = trader
        self.strategy = strategy
        self.data_provider = data_provider

        # Internal stores
        self.df_store: Dict[tuple, deque] = defaultdict(lambda: deque(maxlen=200))
        self.order_books: Dict[str, dict] = defaultdict(dict)

        # Async plumbing
        self.queue: asyncio.Queue = asyncio.Queue()
        self.ws: Optional[websockets.WebSocketClientProtocol] = None

        self.is_running = False
        self._retries = 0
        self._max_retries = int(config.get("WS_MAX_RETRIES", 5))

        # Task handles for cleanup
        self._hb_task: Optional[asyncio.Task] = None
        self._listener_task: Optional[asyncio.Task] = None
        self._consumer_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_message_callback(self, cb: Callable[..., asyncio.Future]) -> None:
        """Register/replace the coroutine to process inbound ticker messages."""
        self._message_callback = cb

    def max_retries_reached(self) -> bool:
        return self._retries >= self._max_retries

    async def run(self) -> None:
        """Reconnect loop with simple backoff."""
        while not self.max_retries_reached():
            try:
                await self.connect()
                break  # graceful close
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._retries += 1
                self.logger.warning("Reconnect #%s after error: %s", self._retries, exc)
                await asyncio.sleep(min(5 * self._retries, 30))
        self.is_running = False

    async def connect(self) -> None:
        if not self._ws_url:
            raise RuntimeError("WebSocket URL not configured.")
        self.is_running = True

        async with websockets.connect(self._ws_url, ping_interval=None) as ws:
            self.ws = ws
            self.logger.info("✅ Connected to WS: %s", self._ws_url)
            self.logger.info("✅ WS connect → %s", self._ws_url)

            # Heartbeat
            self._hb_task = asyncio.create_task(self._heartbeat())

            await self.subscribe_to_channels()

            # Spawn listener & consumer
            self._listener_task = asyncio.create_task(self.listen_messages())
            self._consumer_task = asyncio.create_task(self.process_message_queue())

            # Keep this coroutine alive until shutdown
            while self.is_running:
                await asyncio.sleep(1)

    async def graceful_shutdown(self) -> bool:
        """Stop loops and close resources cleanly."""
        self.is_running = False

        # Unblock consumer
        await self.queue.put(None)

        # Cancel tasks
        for task in (self._hb_task, self._listener_task, self._consumer_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass

        return True

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    
    async def _heartbeat(self, interval: int = 25) -> None:
        while self.is_running and self.ws:
            try:
                pong = await self.ws.ping()
                await asyncio.wait_for(pong, timeout=10)
            except Exception as e:
                self.logger.warning("Heartbeat ping failed: %s", e)
                break
            await asyncio.sleep(interval)

    async def subscribe_to_channels(self) -> None:
        depth_level = int(self.config.get("DEPTH_LEVEL", 50))
        for symbol in self.symbols:
            for tf in self.timeframes:
                # ------------------------------------------------------
                # 1) PREFILL (use canonical key for the REST helper)
                # ------------------------------------------------------
                await self.prefill_data(symbol, tf)

                # ------------------------------------------------------
                # 2) BUILD WS MESSAGES
                # ------------------------------------------------------
                # Use the *env‑provided* WS code.  Fallback to REST code,
                # and only finally to the canonical key if nothing exists.
                #ws_tf = (
                #    self.timeframe_mapping.get(tf)      # e.g. "5min", "1hr"
                #    or self.rest_code_map.get(tf)       # e.g. "minute5", "hour1"
                #    or tf                               # last‑ditch: "5m"
                #)
                ws_tf = self.timeframe_mapping.get(tf)

                # kbar
                kbar_msg = json.dumps({
                    "action": "subscribe",
                    "subscribe": "kbar",
                    "kbar": ws_tf,
                    "pair": symbol
                })
                new_var = kbar_msg
                await self.ws.send(new_var)
                self.logger.info("▶ WS SUBSCRIBE for OHLC→ %s", json.dumps(new_var))

                # depth
                depth_msg = json.dumps({
                    "action": "subscribe",
                    "subscribe": "depth",
                    "pair": symbol,
                    "depth": depth_level
                })
                self.logger.info("▶ WS SUBSCRIBE for Depth %s", json.dumps(depth_msg))
                await self.ws.send(depth_msg)

                # Prefill REST data for this TF
                await self.prefill_data(symbol, tf)

    async def prefill_data(self, symbol: str, timeframe: str) -> None:
        canonical_tf = normalize_tf(timeframe)
        rest_tf = self.rest_code_map.get(canonical_tf)

        if not rest_tf:
            self.logger.warning("No REST code for timeframe %s; skipping prefill", timeframe)
            return

        self.logger.debug("Prefill %s %s (REST:%s)", symbol, canonical_tf, rest_tf)

        df = fetch_initial_kline(
            symbol=symbol,
            interval=canonical_tf,
            size=200,
            rest_code_map=self.rest_code_map,
            logger=self.logger,
        )
        self.df_store[(symbol, timeframe)] = deque(df.to_dict("records"), maxlen=200)

    async def listen_messages(self) -> None:
        """Read raw frames from WS and push to queue."""
        import websockets
        try:
            async for raw in self.ws:
                await self.queue.put(raw)
        except websockets.exceptions.ConnectionClosed as e:
            # 1000 = normal close, 1006 = timeout / no close frame
            level = self.logger.warning if e.code not in (1000, 1006) else self.logger.info
            level("WS closed (code=%s reason=%s)", e.code, e.reason)
        except Exception:
            self.logger.exception("Listen loop crashed")
        finally:
            self.is_running = False
            # ensure queue consumer can exit
            await self.queue.put(None)

    async def process_message_queue(self) -> None:
        """Consume raw websocket frames from the queue and handle them."""
        while self.is_running:
            try:
                raw = await self.queue.get()
                if raw is None:  # sentinel to exit
                    break
                await self._handle_ws_message(raw)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.logger.exception("Queue consumer crashed: %s", exc)

    async def _handle_ws_message(self, raw_msg: str) -> None:
        """Internal per-message handler (NOT the core handler)."""
        try:
            msg = json.loads(raw_msg)
        except Exception:
            self.logger.warning("Malformed WS payload: %s", raw_msg)
            return

        # Ping / pong
        ping_val = msg.get("ping")
        if ping_val:
            await self.ws.send(json.dumps({"action": "pong", "pong": ping_val}))
            return

        # Server error payloads
        if msg.get("status") == "error":
            self.logger.warning("WS error: %s", msg.get("message"))
            return

        subscribe_type = msg.get("subscribe", "")
        data = msg.get("data", {})

        # Handle kbar & depth locally
        if subscribe_type == "kbar":
            symbol = data.get("symbol")
            kbar_tf = msg.get("kbar")
            canonical_tf = normalize_tf(kbar_tf or "")
            key = (symbol, canonical_tf)
            self.df_store[key].append(data)

            # Local indicator calc (optional)
            df = pd.DataFrame(self.df_store[key])
            df = (
                IndicatorCalculator(df)
                .calculate_rsi()
                .calculate_macd()
                .calculate_bollinger()
                .get_df()
            )

        elif subscribe_type == "depth":
            symbol = data.get("symbol")
            if symbol:
                self.order_books[symbol] = data

        # Forward ONLY ticker.* to core.message_handler
        if self._message_callback and isinstance(msg, dict):
            sub = msg.get("subscribe", "")
            if isinstance(sub, str) and sub.startswith("ticker."):
                try:
                    await self._message_callback(msg, self.df_store, self.order_books)
                except Exception as cb_exc:
                    self.logger.exception("External message callback failed: %s", cb_exc)
