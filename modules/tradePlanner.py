
from sl_tp_planner import SLTPPlanner
import pandas as pd
from typing import Dict


class TradePlanner:
    """
    Handles trade planning using structured SL/TP logic with multi-timeframe support.
    """

    def __init__(self):
        pass  # Customize this if you need initialization logic

    def generate_sl_tp_plan(self, entry_price: float, symbol: str, data_by_timeframe: Dict[str, pd.DataFrame],
                            ma_col: str = 'ma_50', fib_levels: dict = None, min_rr: float = 2.0) -> dict:
        """
        Generate structured SL/TP plan using SLTPPlanner across multiple timeframes.
        """
        planner = SLTPPlanner(entry_price=entry_price, symbol=symbol, data_by_timeframe=data_by_timeframe)

        # Apply planning methods
        planner.set_by_swing_levels()
        planner.set_by_atr()
        planner.set_by_moving_average(ma_column_name=ma_col)

        if fib_levels:
            planner.set_by_fibonacci(fib_levels)

        planner.add_trailing_stop(distance=entry_price * 0.01)  # Example: 1% trailing stop
        planner.validate_risk_reward(min_rr=min_rr)

        return planner.get_plan()

    def select_best_sl_tp(self, plan: dict) -> dict:
        """
        Selects the SL/TP method with the highest valid Risk-Reward Ratio.
        """
        best_method = None
        best_rrr = 0
        best_result = {}

        for method, values in plan.items():
            if not isinstance(values, dict):
                continue
            if values.get('valid'):
                rrr = values.get('RRR', 0)
                if rrr > best_rrr:
                    best_method = method
                    best_rrr = rrr
                    best_result = values.copy()
                    best_result['method'] = method

        return best_result if best_method else {"error": "No valid SL/TP method found"}
