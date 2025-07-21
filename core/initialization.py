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

import os
from typing import Dict, Optional

from dotenv import load_dotenv

from modules.websocket_client_real_time import WebSocketClient
from modules.strategy import TradePlanner
from modules.trader import Trader
from utils.logger import setup_logger


def load_configuration(env_path: str = "config.env") -> Dict:
    """
    Load configuration values from an ``.env`` file.

    The function parses primitive values (strings, lists) straight from
    the environment, and also reconstructs nested dictionaries for
    timeframe code mappings and API credentials.

    Parameters
    ----------
    env_path : str, optional
        Filesystem path to the ``.env`` file.  Defaults to ``"config.env"``.

    Returns
    -------
    dict
        A hierarchical configuration dictionary ready to be passed to
        other components.
    """
    # Populate environment from the supplied dotenv file
    load_dotenv(dotenv_path=env_path)

    symbols = os.getenv("SYMBOLS_VALUE", "").split(",")
    timeframes = os.getenv("TIMEFRAMES_VALUE", "").split(",")

    # --- timeframe code maps -------------------------------------------------
    ws_timeframe_codes, rest_timeframe_codes = {}, {}
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
        # Credentials / tokens -------------------------------------------------
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


def initialize_components(
    config: Dict,
    overrides: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """
    Instantiate and wire‑up runtime components.

    Parameters
    ----------
    config : dict
        Configuration dictionary produced by :func:`load_configuration`.
    overrides : dict[str, object], optional
        A mapping of *component_name → custom_instance* allowing tests to
        inject mocks:
        ``initialize_components(cfg, overrides={"logger": DummyLogger()})``

    Returns
    -------
    dict[str, object]
        Dictionary exposing constructed components:

        - ``logger``
        - ``strategy``  (TradePlanner)
        - ``trader``    (Trader)
        - ``websocket_client``
        - ``data_provider`` (if supplied via *overrides*)
    """
    overrides = overrides or {}
    ### Use the caller‑supplied logger if there is one; otherwise, create a new module‑scoped logger.    logger = overrides.get("logger") or setup_logger(__name__)
    strategy = overrides.get("strategy") or TradePlanner()
    trader = overrides.get("trader") or Trader(config=config, logger=logger)
    websocket_client = overrides.get("websocket_client") or WebSocketClient(
        config=config,
        trader=trader,
        strategy=strategy,
        logger=logger,
    )
    data_provider = overrides.get("data_provider")  # may be None

    # Log lifecycle -----------------------------------------------------------
    logger.info("✅ Logger initialized.")
    logger.info("✅ Strategy initialized.")
    logger.info("✅ Trader initialized.")
    logger.info("✅ WebSocketClient initialized.")

    return {
        "logger": logger,
        "strategy": strategy,
        "trader": trader,
        "websocket_client": websocket_client,
        "data_provider": data_provider,
    }
