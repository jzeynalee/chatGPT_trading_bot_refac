"""
message_handler.py
==================

Robust handler for inbound WebSocket messages.

Improvements over the original implementation
---------------------------------------------
* **Input validation** – ignores malformed / unexpected messages.
* **Structured logging** – debug‑logs the entire message before
  processing; errors are logged with stack traces.
* **Graceful failure** – exceptions raised by downstream handlers do not
  crash the WebSocket loop; they are caught and logged.
* **Testability hook** – `process_fn` and `signal_check_fn` can be
  injected (handy for unit tests).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Callable, Awaitable

from utils.logger import setup_logger

logger = setup_logger(__name__)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _is_ticker_message(data: Dict[str, Any]) -> bool:
    """Return *True* if the message is a *ticker* subscription payload."""
    return (
        isinstance(data, dict)
        and "subscribe" in data
        and isinstance(data["subscribe"], str)
        and "ticker" in data["subscribe"]
    )

# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

async def handle_message(
    data: Dict[str, Any],
    df_store: dict,
    order_books: dict | None = None,
    *,
    process_fn: Callable[[Dict[str, Any], str, dict], Awaitable[None]] | None = None,
    signal_check_fn: Callable[[], None] | None = None,
) -> None:
    """Handle a single WebSocket message.

    Parameters
    ----------
    data : dict
        The *already decoded* JSON message.
    df_store : dict
        A symbol‑keyed store of OHLCV DataFrames.
    order_books : dict, optional
        Order‑book snapshots keyed by symbol (may be *None* if not used).
    process_fn : coroutine, optional
        Custom coroutine to process tick data. Falls back to
        ``core.signal_handler.process_tick_data`` if omitted.
    signal_check_fn : callable, optional
        Function that checks + dispatches signals after every tick. Falls
        back to ``core.tick_handler.check_signals``.
    """
    # --------------------------------------------------------------------
    # choose default dependencies lazily (helps with import cycles)
    # --------------------------------------------------------------------
    if process_fn is None:
        from core.signal_handler import process_tick_data as process_fn  # noqa: WPS433 (dyn‑import)
    if signal_check_fn is None:
        from core.tick_handler import check_signals as signal_check_fn  # noqa: WPS433 (dyn‑import)

    # --------------------------------------------------------------------
    # validate + short‑circuit
    # --------------------------------------------------------------------
    if not _is_ticker_message(data):
        logger.debug("⏭️  Non‑ticker message skipped: %s", data)
        return

    symbol = data["subscribe"].split(".")[-1]
    logger.debug("📥 Incoming ticker (%s): %s", symbol, data)

    # --------------------------------------------------------------------
    # main processing with robust error handling
    # --------------------------------------------------------------------
    try:
        await process_fn(data, symbol, df_store)
        signal_check_fn()
    except Exception:  # noqa: BLE001 (broad but logged)
        logger.exception("[DATA HANDLER ERROR] %s", symbol)
