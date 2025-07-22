
# sl_tp_planner.py

import pandas as pd
from typing import Dict


class SLTPPlanner:
    """
    Structured multi-timeframe SL/TP planning class.
    Uses swing points, ATR, MA across multiple timeframes.
    """

    def __init__(self, entry_price: float, symbol: str, data_by_timeframe: Dict[str, pd.DataFrame]):
        """
        :param entry_price: trade entry level
        :param symbol: trading pair (e.g., 'BTC/USDT')
        :param data_by_timeframe: dict of { '15m': df_15m, '1h': df_1h, ... }
        """
        self.entry = entry_price
        self.symbol = symbol
        self.data_by_timeframe = data_by_timeframe
        self.result = {}

    def set_by_swing_levels(self, lookback: int = 50):
        """
        Uses recent swing highs/lows to define SL/TP for each timeframe.
        """
        for tf, df in self.data_by_timeframe.items():
            lows = df['swing_low'].dropna().tail(lookback)
            highs = df['swing_high'].dropna().tail(lookback)

            support_candidates = lows[lows < self.entry]
            resistance_candidates = highs[highs > self.entry]

            support = support_candidates.max() if not support_candidates.empty else self.entry * 0.98
            resistance = resistance_candidates.min() if not resistance_candidates.empty else self.entry * 1.02

            sl = support * 0.995
            tp = resistance * 0.995

            self.result[f'SwingPoints_{tf}'] = {
                'sl': round(sl, 4),
                'tp': round(tp, 4)
            }

    def set_by_atr(self, atr_period: int = 14, multiplier_sl=1.5, multiplier_tp=2.5):
        """
        Sets SL/TP based on ATR range for each timeframe.
        """
        for tf, df in self.data_by_timeframe.items():
            atr = df['high'].rolling(atr_period).max() - df['low'].rolling(atr_period).min()
            latest_atr = atr.iloc[-1]

            sl = self.entry - latest_atr * multiplier_sl
            tp = self.entry + latest_atr * multiplier_tp

            self.result[f'ATR_{tf}'] = {
                'sl': round(sl, 4),
                'tp': round(tp, 4)
            }

    def set_by_moving_average(self, ma_column_name: str = 'ma_50'):
        """
        Uses a specified moving average to define SL/TP for each timeframe.
        Assumes MA is precomputed in each DataFrame.
        """
        for tf, df in self.data_by_timeframe.items():
            if ma_column_name not in df.columns:
                continue  # skip if MA not present

            ma_value = df[ma_column_name].iloc[-1]
            sl = ma_value * 0.99
            tp = self.entry + (self.entry - sl) * 2

            self.result[f'MA_{tf}'] = {
                'sl': round(sl, 4),
                'tp': round(tp, 4)
            }

    def set_by_fibonacci(self, fib_levels_by_tf: Dict[str, Dict[str, float]]):
        """
        Uses externally provided Fibonacci levels (e.g., from swing analysis).
        Format: {'1h': {'fib_61_8': 49.5, 'fib_127_2': 53.0, 'fib_161_8': 54.5}, ...}
        """
        for tf, levels in fib_levels_by_tf.items():
            if tf not in self.data_by_timeframe:
                continue

            fib_61_8 = levels.get('fib_61_8')
            fib_127_2 = levels.get('fib_127_2')
            fib_161_8 = levels.get('fib_161_8')

            if fib_61_8 and fib_127_2 and fib_161_8:
                sl = fib_61_8 * 0.995
                tp = fib_127_2 if abs(fib_127_2 - self.entry) < abs(fib_161_8 - self.entry) else fib_161_8

                self.result[f'Fibonacci_{tf}'] = {
                    'sl': round(sl, 4),
                    'tp': round(tp, 4)
                }

    def add_trailing_stop(self, distance: float):
        """
        Adds trailing stop info (applied globally).
        """
        self.result['TrailingStop'] = round(distance, 4)

    def validate_risk_reward(self, min_rr: float = 2.0):
        """
        Validates all methods in self.result to ensure RR >= min_rr.
        Adds RRR value and flags invalids.
        """
        for method, values in list(self.result.items()):
            if not isinstance(values, dict) or 'sl' not in values or 'tp' not in values:
                continue
            risk = abs(self.entry - values['sl'])
            reward = abs(values['tp'] - self.entry)
            rr = reward / risk if risk != 0 else 0
            self.result[method]['RRR'] = round(rr, 2)
            self.result[method]['valid'] = rr >= min_rr

    def get_plan(self) -> Dict:
        """
        Returns final SL/TP plan across all timeframes.
        """
        return self.result
