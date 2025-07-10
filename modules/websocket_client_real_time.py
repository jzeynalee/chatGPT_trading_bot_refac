import asyncio
import websockets
import json
import requests
import pandas as pd
from core import get_multi_df
from logger import get_logger  # Ensure logger.py is in the same folder or in PYTHONPATH

logger = get_logger("ws_client")

class WebSocketClient:
    def __init__(self, symbols, timeframes, on_message_callback, logger, max_retries: int = 5, retry_delay: float = 5.0):
        self.symbols = symbols
        self.timeframes = timeframes


        self.logger = logger
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        #self.message_callback = None
        self.is_running = False
        self._connection = None
        
        self.on_message_callback = on_message_callback
        self.url = "wss://www.lbkex.net/ws/V2/"
        self.kline_url = "https://api.lbank.info/v2/kline.do"
        self.depth_url = "https://api.lbank.info/v2/depth.do"
        self.df_store = {}       # {symbol: {timeframe: DataFrame}}
        self.order_books = {}    # {symbol: {'bids': [...], 'asks': [...]}}
        
    def set_message_callback(self, callback: on_message_callback):
        """Set the callback for incoming messages."""
        self.message_callback = callback
        

    def fetch_initial_data(self):
        logger.info("Fetching initial kline and order book data...")
        for symbol in self.symbols:
            self.df_store[symbol] = {}
            for tf in self.timeframes:
                try:
                    df = get_multi_df(symbol, tf, limit=200)
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
        """Connect to the WebSocket with reconnection logic."""
        retry_count = 0
        self.is_running = True
        self.fetch_initial_data()
        
        while self.is_running and retry_count <= self.max_retries:
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
                if not self.is_running:
                    break  # Exit if we're shutting down intentionally
                    
                retry_count += 1
                if retry_count > self.max_retries:
                    self.logger.error(f"❌ Max reconnection attempts reached. Giving up.")
                    break
                    
                wait_time = min(self.retry_delay * (2 ** (retry_count - 1)), 60)  # Exponential backoff with max of 60s
                self.logger.warning(f"⚠️ Connection lost ({str(e)}). Attempting reconnect {retry_count}/{self.max_retries} in {wait_time:.1f}s...")
                
                await asyncio.sleep(wait_time)
                
    async def listen(self):
        """Listen for incoming messages and pass them to the callback."""
        while True:
            try:
                message = await self._connection.recv()
                if message and self.message_callback:
                    await self.message_callback(message)
            
            except websockets.exceptions.ConnectionClosed as e:
                if not e.code == 1000:  # Normal closure code is 1000 (clean disconnect)
                    raise e from None  # Re-raise exception to trigger reconnection logic
            
            except Exception as e:
                raise e from None
    
    async def disconnect(self):
        """Cleanly disconnect from the WebSocket."""
        if not hasattr(self, '_connection') or not hasattr(self._connection, 'close'):
            return
            
        try:
            await asyncio.wait_for(self._connection.close(), timeout=2)
            await asyncio.wait_for(asyncio.sleep(0.1), timeout=2) 
            
            if hasattr(self._connection, 'ws_client'):
                await asyncio.wait_for(
                    getattr(self._connection, 'ws_client').close(), 
                    timeout=2,
                )
                
            while not getattr(self._connection, 'closed', True):
                await asyncio.sleep(0.1)
                
            delattr(self._connection, '_closing')
            
            return True
            
        except Exception as exc:  
            return False
            
    async def graceful_shutdown(self):
        """Gracefully shutdown the WebSocket connection."""
        try:
            await super().graceful_shutdown()
            
            tasks_to_cancel += [
                t for t in asyncio.all_tasks() 
                if t is not current_task and "websockets" in str(t)
            ]
            
            for task in tasks_to_cancel:  
                 task.cancel()
                 
                 try:   
                     await task  
                 except Exception:  
                     pass   
                     
                 del task   
                 
             return True   
             
         except Exception:   
             return False  

         finally:   
             setattr(self,'is_running',False)  


