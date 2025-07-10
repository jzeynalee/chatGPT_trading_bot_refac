import asyncio
import websockets
import json
import requests
import pandas as pd
from core import get_multi_df
from logger import get_logger  # Ensure logger.py is in the same folder or in PYTHONPATH

logger = get_logger("ws_client")

class WebSocketClient:
    def __init__(self, symbols, timeframes, on_message_callback):
        self.symbols = symbols
        self.timeframes = timeframes
        self.on_message_callback = on_message_callback
        self.url = "wss://www.lbkex.net/ws/V2/"
        self.kline_url = "https://api.lbank.info/v2/kline.do"
        self.depth_url = "https://api.lbank.info/v2/depth.do"
        self.df_store = {}       # {symbol: {timeframe: DataFrame}}
        self.order_books = {}    # {symbol: {'bids': [...], 'asks': [...]}}

    def fetch_initial_data(self):
        logger.info("Fetching initial kline and order book data...")
        for symbol in self.symbols:
            self.df_store[symbol] = {}
            for tf in self.timeframes:
                try:
                    df = get_multi_df(symbol, tf, limit=100)
                    if df is not None:
                        self.df_store[symbol][tf] = df
                        logger.info(f"[INIT] Loaded OHLCV for {symbol}-{tf}")
                except Exception as e:
                    logger.warning(f"[INIT ERROR] OHLCV {symbol}-{tf}: {e}")
            try:
                response = requests.get(self.depth_url, params={"symbol": symbol, "size": 200})
                ob_data = response.json()
                if ob_data.get("result") == "true":
                    self.order_books[symbol] = {
                        "asks": ob_data.get("asks", []),
                        "bids": ob_data.get("bids", [])
                    }
                    logger.info(f"[INIT] Loaded order book for {symbol}")
                else:
                    logger.warning(f"[ORDER BOOK FAIL] {symbol} returned: {ob_data}")
            except Exception as e:
                logger.error(f"[ORDER BOOK ERROR] {symbol}: {e}")

    async def connect(self):
        self.fetch_initial_data()
        try:
            async with websockets.connect(self.url) as ws:
                for symbol in self.symbols:
                    await ws.send(json.dumps({
                        "action": "subscribe",
                        "subscribe": f"ticker.{symbol}"
                    }))
                    await ws.send(json.dumps({
                        "action": "subscribe",
                        "subscribe": f"depth.{symbol}"
                    }))
                    logger.info(f"[WS] Subscribed to ticker & depth for {symbol}")

                logger.info("[WS] WebSocket connected and listening...")

                while True:
                    try:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        await self.on_message_callback(data, self.df_store, self.order_books)
                    except Exception as e:
                        logger.error(f"[WS MESSAGE ERROR] {e}")
                        await asyncio.sleep(3)

        except Exception as e:
            logger.critical(f"[WS CONNECTION FAILED] {e}")
