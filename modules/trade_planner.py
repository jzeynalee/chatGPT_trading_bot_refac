from __future__ import annotations
from typing import Dict, Optional, List

from utils.logger import setup_logger
from modules.sl_tp_planner import SLTPPlanner

logger = setup_logger(__name__)

class TradePlanner:
    """Coordinator for SL/TP planning and optional execution."""
    def __init__(self, data_provider=None, trader=None):
        self.data_provider = data_provider
        self.trader = trader

    def plan_sl_tp(self, symbol: str, entry_price: float,
                   timeframes: Optional[List[str]] = None,
                   fib_levels: Optional[dict] = None) -> Dict[str, float]:
        timeframes = timeframes or ["15m","1h","4h"]
        data_by_tf = {}
        if self.data_provider:
            for tf in timeframes:
                df = self.data_provider.get_ohlcv(symbol, tf)
                data_by_tf[tf] = df
        else:
            logger.warning("No data_provider supplied; using empty data_by_tf.")

        planner = SLTPPlanner(entry_price=entry_price, symbol=symbol,
                              data_by_timeframe=data_by_tf,
                              fib_levels=fib_levels or {})
        planner.set_by_swing_levels()
        planner.set_by_atr()
        planner.validate_risk_reward()
        plan = planner.get_plan()

        chosen = next((v for v in plan.values() if v.get("valid")), None)
        if not chosen and plan:
            chosen = next(iter(plan.values()))

        sl = float(chosen.get("sl", entry_price*0.98))
        tp = float(chosen.get("tp", entry_price*1.02))
        reward = tp - entry_price
        return {
            "stop_loss": sl,
            "take_profit_1": tp,
            "take_profit_2": entry_price + reward*1.5,
            "take_profit_3": entry_price + reward*2.0,
        }

    def execute_trade(self, symbol: str, entry_price: float, sl: float, tp: float, **kwargs):
        if not self.trader:
            logger.warning("No trader injected; skipping order execution.")
            return
        self.trader.place_order(symbol=symbol, entry=entry_price, sl=sl, tp=tp, **kwargs)
