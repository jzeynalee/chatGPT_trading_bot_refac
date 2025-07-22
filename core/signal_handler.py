from __future__ import annotations
from datetime import datetime
from typing import Any, Callable, Dict

from pydantic import ValidationError
from models.signal import TradeSignal
from utils.logger import setup_logger

logger = setup_logger(__name__)

async def handle_new_signal(
    signal: Dict[str, Any],
    *,
    dispatcher=None,
    format_fn: Callable[[TradeSignal], str] | None = None,
    trade_planner=None,
) -> None:
    """Validate/enrich (SLTP) with Pydantic and dispatch."""
    from notifiers.SignalDispatcher import SignalDispatcher

    needed = {"stop_loss","take_profit_1","take_profit_2","take_profit_3"}
    if not needed.issubset(signal):
        if trade_planner is None:
            from modules.trade_planner import TradePlanner
            trade_planner = TradePlanner()
        sltp = trade_planner.plan_sl_tp(signal["symbol"], float(signal["price"]))
        signal.update(sltp)
        signal.setdefault("timestamp", datetime.utcnow().timestamp())

    try:
        sig_model = TradeSignal(**signal)
    except ValidationError as ve:
        logger.warning("Signal validation failed: %s", ve)
        return

    dispatcher = dispatcher or SignalDispatcher()
    format_fn = format_fn or _default_format

    try:
        msg = format_fn(sig_model)
        await dispatcher.dispatch(msg)
        logger.info("🚀 Dispatched signal for %s", sig_model.symbol)
    except Exception:
        logger.exception("Failed to dispatch signal: %s", sig_model.model_dump())

def _default_format(sig: TradeSignal) -> str:
    ts = datetime.utcfromtimestamp(sig.timestamp).strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        f"#TRADE\n"
        f"Symbol: {sig.symbol}\n"
        f"Direction: {sig.direction.upper()}\n"
        f"Entry: {sig.price}\n"
        f"SL: {sig.stop_loss}\n"
        f"TP1: {sig.take_profit_1} | TP2: {sig.take_profit_2} | TP3: {sig.take_profit_3}\n"
        f"Time: {ts}"
    )
