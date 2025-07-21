import os
from dotenv import load_dotenv
from modules.websocket_client_real_time import WebSocketClient
from modules.strategy import TradePlanner
from modules.trader import Trader
from utils.logger import setup_logger

def load_configuration():
    load_dotenv(dotenv_path="config.env")

    # Parse symbols and timeframes
    symbols = os.getenv("SYMBOLS_VALUE", "").split(",")
    timeframes = os.getenv("TIMEFRAMES_VALUE", "").split(",")

    # Extract nested timeframe code dictionaries
    ws_timeframe_codes = {}
    rest_timeframe_codes = {}
    for key, value in os.environ.items():
        if key.startswith("WEBSOCKET_TIMEFRAME_CODES_"):
            tf = key.replace("WEBSOCKET_TIMEFRAME_CODES_", "").lower()
            ws_timeframe_codes[tf] = value
        elif key.startswith("REST_TIMEFRAME_CODES_"):
            tf = key.replace("REST_TIMEFRAME_CODES_", "").lower()
            rest_timeframe_codes[tf] = value

    return {
        "SYMBOLS": symbols,
        "TIMEFRAMES": timeframes,
        "WEBSOCKET_TIMEFRAME_CODES": ws_timeframe_codes,
        "REST_TIMEFRAME_CODES": rest_timeframe_codes,
        "TELEGRAM": {
            "token": os.getenv("TELEGRAM_TOKEN"),
            "chat_id": os.getenv("TELEGRAM_CHAT_ID"),
        },
        "TWITTER": {
            "api_key": os.getenv("TWITTER_API_KEY"),
            "api_secret": os.getenv("TWITTER_API_SECRET"),
            "access_token": os.getenv("TWITTER_ACCESS_TOKEN"),
            "access_secret": os.getenv("TWITTER_ACCESS_SECRET"),
        },
        "LINKEDIN": {
            "username": os.getenv("LINKEDIN_USERNAME"),
            "password": os.getenv("LINKEDIN_PASSWORD"),
        },
        "LBANK_API": {
            "api_key": os.getenv("LBANK_API_API_KEY"),
            "api_secret": os.getenv("LBANK_API_API_SECRET"),
        },
    }

def initialize_components(config):
    logger = setup_logger("main")

    strategy = TradePlanner()
    trader = Trader(config=config, logger=logger)
    websocket_client = WebSocketClient(config=config, trader=trader, strategy=strategy, logger=logger)

    return {
        "logger": logger,
        "strategy": strategy,
        "trader": trader,
        "websocket_client": websocket_client
    }
