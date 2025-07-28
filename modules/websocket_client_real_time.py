import asyncio
import json
import logging
from collections import defaultdict, deque
from typing import Any, Callable, Dict, Optional

import pandas as pd
import websockets

from utils.utils import fetch_initial_kline
from modules.indicator import IndicatorCalculator
from utils.timeframe import normalize_tf
from utils.logger import setup_logger



class ConfigManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def get_ws_url(self) -> str:
        return (
            self.config.get("LBANK_API", {}).get("websocket_url")
            or self.config.get("WEBSOCKET_URL")
            or "wss://www.lbkex.net/ws/V2/"
        )

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def get_timeframe_mapping(self) -> Dict[str, str]:
        return (
            self.config.get("TIMEFRAME_MAPPING")
            or self.config.get("WEBSOCKET_TIMEFRAME_CODES", {})
            or {}
        )

    def get_rest_code_map(self) -> Dict[str, str]:
        return (
            self.config.get("rest_code_map")
            or self.config.get("REST_TIMEFRAME_CODES")
            or {}
        )

    def get_symbols(self) -> list:
        return self.config.get("symbols") or self.config.get("SYMBOLS") or []

    def get_timeframes(self) -> list:
        return self.config.get("timeframes") or self.config.get("TIMEFRAMES") or []

    def get_max_retries(self) -> int:
        return int(self.config.get("WS_MAX_RETRIES", 5))

    def get_depth_level(self) -> int:
        return int(self.config.get("DEPTH_LEVEL", 50))


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
        self.config_mgr = ConfigManager(config)
        
        self.logger = logger if logger else setup_logger("WebSocketClient")
        self.logger.info("✅ WebSocketClient initialized with URL: %s", self.url)
        
        self._message_callback = message_callback

        self.url = self.config_mgr.get_ws_url()

        self.timeframe_mapping = self.config_mgr.get_timeframe_mapping()
        self.rest_code_map = self.config_mgr.get_rest_code_map()
        self.symbols = self.config_mgr.get_symbols()
        self.timeframes = self.config_mgr.get_timeframes()

        self.trader = trader
        self.strategy = strategy
        self.data_provider = data_provider

        self.df_store: Dict[tuple, IndicatorCalculator] = {}
        self.order_books: Dict[str, dict] = defaultdict(dict)

        self.queue: asyncio.Queue = asyncio.Queue()
        self.ws: Optional[websockets.WebSocketClientProtocol] = None

        self.is_running = False
        self._stop = False
        self._retries = 0
        self._max_retries = self.config_mgr.get_max_retries()

        self._hb_task: Optional[asyncio.Task] = None
        self._listener_task: Optional[asyncio.Task] = None
        self._consumer_task: Optional[asyncio.Task] = None

    def set_message_callback(self, cb: Callable[..., asyncio.Future]) -> None:
        self._message_callback = cb

    def stop(self) -> None:
        self._stop = True

    async def run(self) -> None:
        backoff = 1
        while not self._stop:
            try:
                await self._connect_once()
                backoff = 1
            except Exception as exc:
                self.logger.exception("WS session crashed: %s", exc)
            if self._stop:
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
        self.is_running = False

    async def _connect_once(self) -> None:
        self.is_running = True
        async with websockets.connect(self.url, ping_interval=None) as ws:
            self.ws = ws
            self.logger.info("✅ WS connect → %s", self.url)
            await self.prefill_all_data()
            await self.subscribe_all()
            self._listener_task = asyncio.create_task(self.listen_messages())
            self._consumer_task = asyncio.create_task(self.process_message_queue())
            self._hb_task = asyncio.create_task(self._heartbeat())
            while self.is_running:
                await asyncio.sleep(1)
        self.logger.info("WS session ended, will reconnect…")

    async def graceful_shutdown(self) -> bool:
        self._stop = True
        self.is_running = False
        await self.queue.put(None)
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

    async def _heartbeat(self, interval: int = 25) -> None:
        while self.is_running and self.ws:
            try:
                pong = await self.ws.ping()
                await asyncio.wait_for(pong, timeout=10)
            except Exception as e:
                self.logger.warning("Heartbeat ping failed: %s", e)
                self.is_running = False
                try:
                    await self.ws.close()
                except Exception:
                    pass
                break
            await asyncio.sleep(interval)

    async def prefill_all_data(self) -> None:
        for symbol in self.symbols:
            for tf in self.timeframes:
                await self.prefill_data(symbol, tf)

    async def subscribe_all(self) -> None:
        depth_level = self.config_mgr.get_depth_level()
        for symbol in self.symbols:
            for tf in self.timeframes:
                ws_tf = self.timeframe_mapping.get(tf)
                if ws_tf is None:
                    self.logger.warning("No WS code for timeframe %s – skipping", tf)
                    continue
                await self.send_subscribe_msg(symbol, ws_tf, depth_level)

    async def send_subscribe_msg(self, symbol: str, ws_tf: str, depth_level: int):
        kbar_msg = {
            "action": "subscribe",
            "subscribe": "kbar",
            "kbar": ws_tf,
            "pair": symbol
        }
        await self.ws.send(json.dumps(kbar_msg))

        depth_msg = {
            "action": "subscribe",
            "subscribe": "depth",
            "pair": symbol,
            "depth": depth_level
        }
        await self.ws.send(json.dumps(depth_msg))

    async def prefill_data(self, symbol: str, timeframe: str) -> None:
        canonical_tf = normalize_tf(timeframe)
        rest_tf = self.rest_code_map.get(canonical_tf)
        if not rest_tf:
            self.logger.warning("No REST code for timeframe %s; skipping prefill", timeframe)
            return
        df = fetch_initial_kline(
            symbol=symbol,
            interval=canonical_tf,
            size=200,
            rest_code_map=self.rest_code_map,
            logger=self.logger,
        )
        calc = IndicatorCalculator(df)
        calc.run_all()
        self.df_store[(symbol, timeframe)] = calc

    async def listen_messages(self) -> None:
        try:
            async for raw in self.ws:
                await self.queue.put(raw)
        except websockets.exceptions.ConnectionClosed as e:
            level = self.logger.warning if e.code not in (1000, 1006) else self.logger.info
            level("WS closed (code=%s reason=%s)", e.code, e.reason)
        except Exception:
            self.logger.exception("Listen loop crashed")
        finally:
            self.is_running = False
            await self.queue.put(None)

    async def process_message_queue(self) -> None:
        while True:
            try:
                raw = await self.queue.get()
                if raw is None:
                    break
                await self._handle_ws_message(raw)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.logger.exception("Queue consumer crashed: %s", exc)

    async def _handle_ws_message(self, raw_msg: str) -> None:
        try:
            msg = json.loads(raw_msg)
        except Exception:
            self.logger.warning("Malformed WS payload: %s", raw_msg)
            return

        ping_val = msg.get("ping")
        if ping_val:
            await self.ws.send(json.dumps({"action": "pong", "pong": ping_val}))
            return

        if msg.get("status") == "error":
            self.logger.warning("WS error: %s", msg.get("message"))
            return

        subscribe_type = msg.get("subscribe", "")
        data = msg.get("data", {})

        if subscribe_type == "kbar":
            symbol = data.get("symbol")
            kbar_tf = msg.get("kbar")
            canonical_tf = normalize_tf(kbar_tf or "")
            key = (symbol, canonical_tf)

            calc = self.df_store.get(key)
            if calc:
                calc.update(data)
                calc.run_all()

        elif subscribe_type == "depth":
            symbol = data.get("symbol")
            if symbol:
                self.order_books[symbol] = data

        if self._message_callback and isinstance(msg, dict):
            sub = msg.get("subscribe", "")
            if isinstance(sub, str) and sub.startswith("ticker."):
                try:
                    await self._message_callback(msg, self.df_store, self.order_books)
                except Exception as cb_exc:
                    self.logger.exception("External message callback failed: %s", cb_exc)
