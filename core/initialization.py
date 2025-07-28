"""
core/initialization.py
----------------------
Loads configuration from .env, normalizes symbols/timeframes, and wires all
runtime components with simple dependency‑injection (DI) overrides.
"""

from __future__ import annotations

import os
import logging
from typing import Dict, Optional

from dotenv import load_dotenv

from utils.logger import setup_logger
from modules.websocket_client_real_time import WebSocketClient
from modules.trader import Trader
from modules.trade_planner import TradePlanner
from utils.timeframe import normalize_tf
from utils.config_manager import ConfigManager



def load_configuration(env_path: str = "config.env") -> Dict:
    """
    Load settings from an .env-style file and return a structured config dict.
    """
    log = logging.getLogger(__name__)
    load_dotenv(dotenv_path=env_path)  
    log.debug("my_config_items:   %s", os.environ.items())

    symbols_raw = os.getenv("SYMBOLS", "")
    timeframes_raw = os.getenv("TIMEFRAMES", "")

    # Build timeframe code maps from env like REST_TIMEFRAME_CODES_1H=hour1
    ws_codes: Dict[str, str] = {}
    rest_codes: Dict[str, str] = {}
    for key, val in os.environ.items():
        if key.startswith("WEBSOCKET_TIMEFRAME_CODES_"):
            raw_ws_tf = key.replace("WEBSOCKET_TIMEFRAME_CODES_", "").lower()
            tf = normalize_tf(raw_ws_tf) 
            ws_codes[tf] = val
        elif key.startswith("REST_TIMEFRAME_CODES_"):
            raw_rest_tf = key.replace("REST_TIMEFRAME_CODES_", "").lower()
            tf = normalize_tf(raw_rest_tf) 
            rest_codes[tf] = val
    log.debug("WS map keys:   %s", list(ws_codes.keys()))
    log.debug("REST map keys: %s", list(rest_codes.keys()))

    #new by chatGPT#conf["TIMEFRAMES"] = [normalize_tf(t.strip()) for t in timeframes_raw.split(",") if t.strip()]
    conf: Dict[str, object] = {
        "SYMBOLS": [s.strip().lower() for s in symbols_raw.split(",") if s.strip()],
        "TIMEFRAMES": [normalize_tf(t.strip()) for t in timeframes_raw.split(",") if t.strip()],
        "WEBSOCKET_TIMEFRAME_CODES": ws_codes,
        "REST_TIMEFRAME_CODES": rest_codes,

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
            "base_url": os.getenv("LBANK_API_BASE_URL", "https://api.lbank.info"),
            "websocket_url": os.getenv("LBANK_API_WEBSOCKET_URL", ""),
        },
        "ACCOUNT": {
            "equity": float(os.getenv("ACCOUNT_EQUITY", "0") or 0),
        },
        "WS_MAX_RETRIES": int(os.getenv("WS_MAX_RETRIES", "5")),
        "DEPTH_LEVEL": int(os.getenv("DEPTH_LEVEL", "50")),
    }

    # Alias for legacy code that expects `rest_code_map`
    conf["rest_code_map"] = conf.get("REST_TIMEFRAME_CODES", {})

    # Optional debug
    log = logging.getLogger(__name__)
    log.debug("Parsed SYMBOLS: %s", conf["SYMBOLS"])
    log.debug("Parsed TIMEFRAMES: %s", conf["TIMEFRAMES"])

    return conf


def initialize_components(
    config: Dict,
    overrides: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """
    Construct and wire together all runtime components (supports DI via overrides).

    Keys you can override:
    {"logger", "strategy", "trader", "websocket_client", "data_provider"}
    """
    overrides = overrides or {}
    config = ConfigManager(config)#: Dict[str, Any]) -> None

    # 1) Logger
    logger = overrides.get("logger") or setup_logger(__name__)

    # 2) Strategy (TradePlanner) – handle possible 'equity' arg via try/except
    strategy = overrides.get("strategy")
    if strategy is None:
        try:
            equity = config.get("ACCOUNT", {}).get("equity", 0.0)
            strategy = TradePlanner(equity=equity)
        except TypeError:
            strategy = TradePlanner()

    # 3) Trader – pass only what the ctor accepts
    trader = overrides.get("trader")
    if trader is None:
        api_cfg = config.get("LBANK_API", {})
        trader = Trader(
            api_key=api_cfg.get("api_key", ""),
            secret_key=api_cfg.get("api_secret", ""),
            base_url=api_cfg.get("base_url", "https://api.lbank.info"),
            logger=logger,
        )

    # 4) Optional data provider
    data_provider = overrides.get("data_provider")

    # 5) WebSocket client – pass only accepted kwargs
    websocket_client = overrides.get("websocket_client")
    if websocket_client is None:
        from core.message_handler import handle_message  # lazy import to avoid cycles
        import inspect

        candidate_args = {
            "config": config,
            "logger": logger,
            "trader": trader,
            "strategy": strategy,
            "data_provider": data_provider,
            "message_callback": handle_message,
        }
        sig = inspect.signature(WebSocketClient.__init__)
        ws_kwargs = {k: v for k, v in candidate_args.items() if k in sig.parameters}
        websocket_client = WebSocketClient(**ws_kwargs)

    logger.info("✅ Logger initialized.")
    logger.info("✅ Strategy initialized: %s", strategy.__class__.__name__)
    logger.info("✅ Trader initialized.")
    logger.info("✅ WebSocketClient initialized.")

    return {
        "logger": logger,
        "strategy": strategy,
        "trader": trader,
        "websocket_client": websocket_client,
        "data_provider": data_provider,
    }
