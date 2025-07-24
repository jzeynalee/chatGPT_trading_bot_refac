import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from typing import Any, Callable, Optional, Dict

import pandas as pd
import websockets

from modules.indicator import IndicatorCalculator
from modules.strategy import strategyEngine  # original import kept
from utils.utils import fetch_initial_kline


class WebSocketClient:
    def __init__(
        self,
        config: Dict[str, Any],
        logger: Optional[logging.Logger] = None,
        message_callback: Optional[Callable[..., asyncio.Future]] = None,
        strategy: Any = None,
    ):
        # ---- config & misc -------------------------------------------------
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.rest_code_map = (
            config.get("rest_code_map")
            or config.get("REST_TIMEFRAME_CODES")
            or {}
        )
        if not self.rest_code_map and self.logger:
            self.logger.warning("No rest_code_map / REST_TIMEFRAME_CODES in config; timeframe conversion may fail.")

        self._message_callback = message_callback
        self.url = (
            config.get("LBANK_API", {}).get("websocket_url")
            or config.get("WEBSOCKET_URL")
            or "wss://www.lbkex.net/ws/V2/"
        )
        self._ws_url = self.url

        # Original hardcoded URL kept as default, but allow override
        self.url = config.get("WEBSOCKET_URL", "wss://www.lbkex.net/ws/V2/")

        # Fallbacks for various key cases
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
        self.timeframe_mapping = (
            config.get("timeframe_mapping")
            or config.get("TIMEFRAME_MAPPING")
            or config.get("WEBSOCKET_TIMEFRAME_CODES", {})
            or {}
        )

        # Data stores
        self.df_store: Dict[tuple, deque] = defaultdict(lambda: deque(maxlen=200))
        self.order_books: Dict[str, dict] = defaultdict(dict)
        self.queue: asyncio.Queue = asyncio.Queue()
        self.ws = None

        # Strategy (DI or build)
        if strategy is not None:
            self.strategy = strategy
        else:
            # try to satisfy possible multi_df parameter
            try:
                self.strategy = strategyEngine(multi_df=self.df_store)
            except TypeError:
                self.strategy = strategyEngine()

        # Runtime state for reconnection logic
        self.is_running: bool = False
        self._retries: int = 0
        self._max_retries: int = int(config.get("WS_MAX_RETRIES", 5))

    # ----------------------------------------------------------------------
    # Public helpers / DI hooks
    # ----------------------------------------------------------------------

    def _tf_ws(self, tf: str) -> str:
        """Map canonical tf (e.g. '1h') to WS code; fallback to tf itself."""
        return self.timeframe_mapping.get(tf, tf)

    def _tf_rest(self, tf: str) -> str:
        """Map canonical tf to REST code ('hour1', etc.)."""
        return self.rest_code_map.get(tf, tf)

    def set_message_callback(self, cb: Callable[..., asyncio.Future]) -> None:
        """Register an external coroutine to process each inbound WS message."""
        self._message_callback = cb

    def max_retries_reached(self) -> bool:
        return self._retries >= self._max_retries

    # ----------------------------------------------------------------------
    # Main run loop
    # ----------------------------------------------------------------------
    
    async def run(self) -> None:
        """Reconnect loop with backoff until stopped or retries exhausted."""
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

    async def connect(self):
        """Establish WS, subscribe, spawn tasks, and keep alive."""
        if not self._ws_url:
            raise RuntimeError("WebSocket URL not configured.")
        self.is_running = True
        try:
            async with websockets.connect(self._ws_url, ping_interval=None) as ws:
                self.ws = ws
                if self.logger:
                    self.logger.info(f"✅ Connected to WS: {self._ws_url}")

                # ← spawn the heartbeat task here
                self._hb_task = asyncio.create_task(self._heartbeat())

                await self.subscribe_to_channels()

                # Spawn consumers
                asyncio.create_task(self.listen_messages())
                asyncio.create_task(self.process_message_queue())

                while self.is_running:
                    await asyncio.sleep(1)
        except Exception as e:
            self.logger.error("Connection failed: %s", e)
            raise

    async def graceful_shutdown(self) -> bool:
        """Stop loops and close socket."""
        self.is_running = False
        # cancel heartbeat if running
        if hasattr(self, "_hb_task"):
            self._hb_task.cancel()
            try:
                await self._hb_task
            except asyncio.CancelledError:
                pass

        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
        return True

    # ----------------------------------------------------------------------
    # Subscriptions / Prefill
    # ----------------------------------------------------------------------
    async def subscribe_to_channels(self):
        for symbol in self.symbols:
            for tf in self.timeframes:
                ws_tf = self._tf_ws(tf)  # already WS style
                kbar_msg = {
                    "action": "subscribe",
                    "subscribe": "kbar",
                    "kbar": ws_tf,
                    "pair": symbol
                }
                await self.ws.send(json.dumps(kbar_msg))

                order_msg = {
                    "action": "subscribe",
                    "subscribe": "depth",
                    "pair": symbol,
                    "depth": int(self.config.get("DEPTH_LEVEL", 50))
                }
                await self.ws.send(json.dumps(order_msg))

                await self.prefill_data(symbol, tf)

    async def prefill_data(self, symbol: str, timeframe: str):
        rest_tf = self._tf_rest(timeframe.lower())
        if not rest_tf:
            if self.logger:
                self.logger.warning("No REST code for timeframe %s; skipping prefill", timeframe)
            return

        if self.logger:
            self.logger.info("📥 Prefilling %s %s via REST code %s", symbol, timeframe, rest_tf)

        self.logger.debug("Calling fetch_initial_kline for %s %s", symbol, timeframe)
        if rest_tf:
            df = fetch_initial_kline(
                symbol, 
                rest_tf, 
                size=200,
                rest_code_map=self.rest_code_map,
                logger=self.logger
                )
            self.df_store[(symbol, timeframe)] = deque(df.to_dict('records'), maxlen=200)
        if timeframe in ("1h", "4h"):
            self.logger.warning("Prefill reached for %s %s", symbol, timeframe)


    # ----------------------------------------------------------------------
    # Message handling
    # ----------------------------------------------------------------------
    async def listen_messages(self):
        try:
            async for msg in self.ws:
                await self.queue.put(msg)
        except websockets.exceptions.ConnectionClosed as e:   # <— catch both OK/Error
            if self.logger:
                self.logger.warning("WS closed unexpectedly: code=%s reason=%s",
                                    getattr(e, 'code', '?'), 
                                    getattr(e, 'reason', '?'))
        
                self.logger.warning("WS closed unexpectedly: code=%s reason=%s", getattr(e, "code", "?"), getattr(e, "reason", "?"))
        except Exception:
             if self.logger:
                self.logger.exception("Listen loop crashed")
        finally:
            self.is_running = False

    async def _heartbeat(self, interval: int = 25):
        '''manual heartbeats every ~25s'''
        while self.is_running and self.ws:
            try:
                await self.ws.ping()
            except Exception as e:
                if self.logger:
                    self.logger.warning("Heartbeat ping failed: %s", e)
                break
            await asyncio.sleep(interval)
    async def handle_ping_pong(self, message: dict):
        ping_value = message.get("ping")
        if ping_value:
            pong_msg = {"action": "pong", "pong": ping_value}
            await self.ws.send(json.dumps(pong_msg))
            self.logger.debug("Responded to ping with pong: %s", ping_value)

    async def _handle_ws_message(self, message: str):
        try:
            msg = json.loads(message)
            await self.handle_ping_pong(msg)

            if 'data' in msg:
                data = msg['data']
                action = msg.get('subscribe')
                symbol = data.get('symbol')

                if action == 'kbar':
                    kbar_tf = msg.get('kbar')
                    key = (symbol, kbar_tf)
                    self.df_store[key].append(data)
                    df = pd.DataFrame(self.df_store[key])
                    df = (
                        IndicatorCalculator(df)
                        .calculate_rsi()
                        .calculate_macd()
                        .calculate_bollinger()
                        .get_df()
                    )
                    signal = self.strategy.evaluate(df)
                    if signal:
                        self.logger.info(f"{symbol}-{kbar_tf} Signal: {signal}")

                elif action == 'depth':
                    self.order_books[symbol] = data  # process order book if needed

                        # External callback hook (ticker only)
            if self._message_callback and isinstance(msg, dict):
                sub = msg.get("subscribe", "")
                if isinstance(sub, str) and sub.startswith("ticker."):
                    try:
                        await self._message_callback(msg, self.df_store, self.order_books)
                    except Exception as cb_exc:
                        self.logger.exception("External message callback failed: %s", cb_exc)

        except Exception as e:
            self.logger.error("Message handling failed: %s\nMessage: %s", e, message)

    async def process_message_queue(self):
        while True:
            msg = await self.queue.get()
            await self._handle_ws_message(msg)