"""
initialization.py
=================

Centralized component initialization for the trading‑bot project.

This module is responsible for:

1. Loading runtime configuration from a **.env** file
   (generated from *config.json* and never committed to Git).
2. Constructing core runtime components – `Logger`, `TradePlanner`,
   `Trader`, and `WebSocketClient`.
3. Providing a **simple Dependency‑Injection (DI) hook** via the
   `overrides` argument so that unit‑tests can swap concrete
   implementations with mocks/stubs without touching production code.

Typical use
-----------
>>> from core.initialization import load_configuration, initialize_components
>>> cfg = load_configuration()
>>> components = initialize_components(cfg)
>>> ws = components["websocket_client"]
>>> ws.run()

All paths, credentials, and runtime options are sourced exclusively from
environment variables defined in *config.env*.
"""

from __future__ import annotations

import os
import logging
import inspect
from typing import Dict, Optional

from dotenv import load_dotenv

from utils.logger import setup_logger
from modules.websocket_client_real_time import WebSocketClient
from modules.trader import Trader
from modules.trade_planner import TradePlanner


def load_configuration(env_path: str = "config.env") -> Dict:
    """Load settings from an .env-style file and return a structured config dict."""
    load_dotenv(dotenv_path=env_path)

    symbols = os.getenv("SYMBOLS_VALUE", "")
    timeframes = os.getenv("TIMEFRAMES_VALUE", "")

    ws_codes, rest_codes = {}, {}
    for key, val in os.environ.items():
        if key.startswith("WEBSOCKET_TIMEFRAME_CODES_"):
            tf = key.replace("WEBSOCKET_TIMEFRAME_CODES_", "").lower()
            ws_codes[tf] = val
        elif key.startswith("REST_TIMEFRAME_CODES_"):
            tf = key.replace("REST_TIMEFRAME_CODES_", "").lower()
            rest_codes[tf] = val


    conf: Dict[str, object] = {
        "SYMBOLS": [s.strip().lower() for s in symbols.split(",") if s.strip()],
        "TIMEFRAMES": [t.strip().lower() for t in timeframes.split(",") if t.strip()],
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
            "websocket_url": os.getenv("LBANK_API_WEBSOCKET_URL", ""),  # optional
        },
        "ACCOUNT": {
            "equity": float(os.getenv("ACCOUNT_EQUITY", "0") or 0),
        },
        "WS_MAX_RETRIES": int(os.getenv("WS_MAX_RETRIES", "5")),
    }

    # ---- Alias to satisfy WebSocketClient expecting `rest_code_map`
    conf["rest_code_map"] = conf.get("REST_TIMEFRAME_CODES", {})
    
    log = logging.getLogger(__name__)
    log.debug("Parsed TIMEFRAMES: %s", conf["TIMEFRAMES"])
    log.debug("Parsed SYMBOLS: %s", conf["SYMBOLS"])

    return conf


def initialize_components(
    config: Dict,
    overrides: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    overrides = overrides or {}

    # 1) Logger first
    logger = overrides.get("logger") or setup_logger(__name__)

    # 2) Strategy / TradePlanner
    strategy = overrides.get("strategy")
    if strategy is None:
        # if your TradePlanner doesn't need equity, this still works
        try:
            equity = config.get("ACCOUNT", {}).get("equity", 0.0)
            strategy = TradePlanner(equity=equity)
        except TypeError:
            strategy = TradePlanner()

    # 3) Trader
    trader = overrides.get("trader")
    if trader is None:
        api_cfg = config.get("LBANK_API", {})
        trader = Trader(
            api_key=api_cfg.get("api_key", ""),
            secret_key=api_cfg.get("api_secret", ""),
            base_url=api_cfg.get("base_url", "https://api.lbank.info"),
            logger=logger,
        )

    # 4) Optional provider (define BEFORE building kwargs)
    data_provider = overrides.get("data_provider")

    # 5) WebSocket client (filter args by signature)
    if "websocket_client" in overrides and overrides["websocket_client"] is not None:
        websocket_client = overrides["websocket_client"]
    else:
        import inspect
        # ⬇️ Lazy import to avoid circular import issues
        from core.message_handler import handle_message
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

    logger.info(f"✅ Logger initialized.")
    logger.info("✅ Strategy initialized: %s", strategy.__class__.__name__)
    logger.info(f"✅ Trader initialized.")
    logger.info(f"✅ WebSocketClient initialized.")

    return {
        "logger": logger,
        "strategy": strategy,
        "trader": trader,
        "websocket_client": websocket_client,
        "data_provider": data_provider,
    }
