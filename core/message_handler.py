"""
message_handler.py
==================
Robust handler for inbound WebSocket *ticker* messages with **strict schema
validation** and detailed logging.  Designed for easy unit‑testing via
injection of custom processing functions.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

from utils.logger import setup_logger

logger = setup_logger(__name__)

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
_REQUIRED_TOP_LEVEL_KEYS: List[str] = [
    "subscribe",  # channel identifier, e.g. "ticker.bt_usdt"
    "tick",       # nested price data payload
]

_REQUIRED_TICK_KEYS: List[str] = [
    "time", "open", "high", "low", "close", "volume"
]


def _is_ticker_channel(channel: str) -> bool:
    """Returns *True* if the subscribe string looks like a ticker channel."""
    return channel.startswith("ticker.")


def _validate_schema(payload: Dict[str, Any]) -> bool:
    """Strictly validate the incoming payload schema.

    Checks:
    1. Required top‑level keys exist.
    2. `subscribe` value appears to be a ticker channel.
    3. `tick` is a dict containing all required price keys.
    4. Numerical fields are *coercible* to `float` (not e.g. ``None`` or
       empty strings).
    """
    # ---- top level --------------------------------------------------------
    for key in _REQUIRED_TOP_LEVEL_KEYS:
        if key not in payload:
            logger.warning("❌ Missing key '%s' in payload: %s", key, payload)
            return False

    subscribe_val = payload["subscribe"]
    if not isinstance(subscribe_val, str) or not _is_ticker_channel(subscribe_val):
        logger.warning("❌ Invalid subscribe channel: %s", subscribe_val)
        return False

    tick = payload["tick"]
    if not isinstance(tick, dict):
        logger.warning("❌ 'tick' must be dict: %s", payload)
        return False

    # ---- tick keys --------------------------------------------------------
    for key in _REQUIRED_TICK_KEYS:
        if key not in tick:
            logger.warning("❌ Missing tick key '%s' in payload: %s", key, payload)
            return False
        # value type check — allow int/float/str‑numeric
        try:
            float(tick[key])
        except (TypeError, ValueError):
            logger.warning("❌ Non‑numeric tick['%s'] value: %s", key, tick[key])
            return False

    return True

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def handle_message(
    data: Dict[str, Any],
    df_store: dict,
    order_books: Optional[dict] = None,
    *,
    process_fn: Callable[[Dict[str, Any], str, dict], Awaitable[None]] | None = None,
    signal_check_fn: Optional[Callable[[], None]] = None,
) -> None:
    """Process a single incoming WebSocket message.

    Parameters
    ----------
    data
        Decoded JSON message from the WebSocket.
    df_store
        Per‑symbol OHLCV DataFrame cache.
    order_books
        Optional per‑symbol order book snapshots.
    process_fn, signal_check_fn
        Dependency‑injection hooks for unit‑testing.
    
    """
    # --------------------------------------------------------------------
    # Validation & early exit
    # --------------------------------------------------------------------
    # Early skip non-ticker or error payloads
    subscribe_val = data.get("subscribe", "")
    if not isinstance(subscribe_val, str) or not subscribe_val.startswith("ticker."):
        logger.debug("⏭️ Non-ticker payload skipped: %s", data)
        return

    if not _validate_schema(data):
        logger.debug("⏭️ Invalid / non‑ticker payload skipped.")
        return

    symbol = data["subscribe"].split(".")[-1]
    logger.debug("📥 Valid ticker (%s): %s", symbol, data)

    # --------------------------------------------------------------------
    # Main processing with fault‑tolerance
    # --------------------------------------------------------------------
    try:
        await process_fn(data, symbol, df_store)
        signal_check_fn()
    except Exception:  # noqa: BLE001 (broad but logged)
        logger.exception("[MESSAGE_HANDLER] processing error for %s", symbol)