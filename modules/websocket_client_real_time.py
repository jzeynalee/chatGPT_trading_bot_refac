import asyncio
import json
import logging
import websockets
import time
import pandas as pd
from collections import defaultdict, deque

from modules.indicator import IndicatorCalculator
from modules.strategy import strategyEngine
from modules.utils import fetch_initial_kline
from secrets_manager import SecretsManager

class WebSocketClient:
    def __init__(self, config):
        self.url = "wss://www.lbkex.net/ws/V2/"
        self.config = config
        self.symbols = config['symbols']
        self.timeframes = config['timeframes']
        self.timeframe_mapping = config['timeframe_mapping']
        self.df_store = defaultdict(lambda: deque(maxlen=200))
        self.order_books = defaultdict(dict)
        self.queue = asyncio.Queue()
        self.ws = None
        self.strategy = StrategyEngine()

    async def connect(self):
        try:
            async with websockets.connect(self.url) as ws:
                self.ws = ws
                await self.subscribe_to_channels()
                asyncio.create_task(self.listen_messages())
                asyncio.create_task(self.process_message_queue())
                while True:
                    await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"Connection failed: {e}")

    async def subscribe_to_channels(self):
        for symbol in self.symbols:
            for tf in self.timeframes:
                ws_tf = tf  # already websocket style from config
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
                    "pair": symbol
                }
                await self.ws.send(json.dumps(order_msg))

                await self.prefill_data(symbol, tf)

    async def prefill_data(self, symbol, timeframe):
        rest_tf = self.timeframe_mapping.get(timeframe)
        if rest_tf:
            df = fetch_initial_kline(symbol, rest_tf, size=200)
            self.df_store[(symbol, timeframe)] = deque(df.to_dict('records'), maxlen=200)

    async def listen_messages(self):
        try:
            async for msg in self.ws:
                await self.queue.put(msg)
        except Exception as e:
            logging.error(f"Listen error: {e}")

    async def handle_ping_pong(self, message):
        ping_value = message.get("ping")
        if ping_value:
            pong_msg = {"action": "pong", "pong": ping_value}
            await self.ws.send(json.dumps(pong_msg))
            logging.debug(f"Responded to ping with pong: {ping_value}")

    async def handle_message(self, message):
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
                    df = IndicatorCalculator(df).calculate_rsi().calculate_macd().calculate_bollinger().get_df()
                    signal = self.strategy.evaluate(df)
                    if signal:
                        logging.info(f"{symbol}-{kbar_tf} Signal: {signal}")

                elif action == 'depth':
                    self.order_books[symbol] = data  # you can process order book here if needed

        except Exception as e:
            logging.error(f"Message handling failed: {e}\nMessage: {message}")

    async def process_message_queue(self):
        while True:
            msg = await self.queue.get()
            await self.handle_message(msg)

    async def graceful_shutdown(self):
        if self.ws:
            await self.ws.close()

    async def run(self):
        await self.connect()
