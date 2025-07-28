import pandas as pd
import numpy as np
from scipy.signal import argrelextrema

class IndicatorCalculator:
    def _normalize_columns(self):
        rename_map = {
        "open": "open_price",
        "high": "high_price",
        "low": "low_price",
        "close": "close_price",
        "volume": "volume"
        }
        self.df.rename(columns=rename_map, inplace=True)

    def __init__(self, df=None):
        self.df = df.copy() if df is not None else pd.DataFrame()
        self._normalize_columns()

    def update(self, new_row: dict):
        self.df = pd.concat([self.df, pd.DataFrame([new_row])], ignore_index=True)
        self._normalize_columns()
        if len(self.df) > 200:
            self.df = self.df.iloc[-200:]

        return self.run_all(latest_only=True)

    def run_all(self, latest_only=False):
        return (
            self.calculate_ichimoku(latest_only)
                .calculate_keltner(latest_only)
                .find_swing_points(latest_only)
                .calculate_fibonacci()
                .calculate_bollinger(latest_only)
                .calculate_rsi(latest_only)
                .calculate_macd(latest_only)
                .detect_candlestick_patterns(latest_only)
        )

    def calculate_ichimoku(self, latest_only=False, tenkan=9, kijun=26, senkou=52):
        high = self.df['high_price']
        low = self.df['low_price']
        close = self.df['close_price']

        last = None if not latest_only else -1
        self.df.loc[:, 'tenkan_sen'] = (high.rolling(tenkan).max() + low.rolling(tenkan).min()) / 2
        self.df.loc[:, 'kijun_sen'] = (high.rolling(kijun).max() + low.rolling(kijun).min()) / 2
        self.df.loc[:, 'senkou_span_a'] = ((self.df['tenkan_sen'] + self.df['kijun_sen']) / 2).shift(kijun)
        self.df.loc[:, 'senkou_span_b'] = ((high.rolling(senkou).max() + low.rolling(senkou).min()) / 2).shift(kijun)
        self.df.loc[:, 'chikou_span'] = close.shift(-kijun)
        return self

    def calculate_keltner(self, latest_only=False, ema_period=20, atr_period=10, multiplier=2):
        df = self.df
        df['ema'] = df['close_price'].ewm(span=ema_period, adjust=False).mean()
        df['tr'] = np.maximum(df['high_price'] - df['low_price'],
                              np.maximum(abs(df['high_price'] - df['close_price'].shift()),
                                         abs(df['low_price'] - df['close_price'].shift())))
        df['atr'] = df['tr'].rolling(atr_period).mean()
        df['keltner_upper'] = df['ema'] + multiplier * df['atr']
        df['keltner_lower'] = df['ema'] - multiplier * df['atr']
        return self

    def find_swing_points(self, latest_only=False, order=3):
        high = self.df['high_price']
        low = self.df['low_price']

        self.df['swing_high'] = np.nan
        self.df['swing_low'] = np.nan

        high_idx = argrelextrema(high.values, np.greater_equal, order=order)[0]
        low_idx = argrelextrema(low.values, np.less_equal, order=order)[0]

        self.df.loc[high_idx, 'swing_high'] = high.iloc[high_idx]
        self.df.loc[low_idx, 'swing_low'] = low.iloc[low_idx]
        return self

    def calculate_fibonacci(self):
        swing_highs = self.df['swing_high'].dropna()
        swing_lows = self.df['swing_low'].dropna()

        if swing_highs.empty or swing_lows.empty:
            for level in ['fib_0', 'fib_23.6', 'fib_38.2', 'fib_50.0', 'fib_61.8', 'fib_78.6', 'fib_100']:
                self.df[level] = np.nan
            return self

        last_high = swing_highs.iloc[-1]
        last_low = swing_lows.iloc[-1]
        diff = last_high - last_low

        levels = {
            'fib_0': last_low,
            'fib_23.6': last_high - 0.236 * diff,
            'fib_38.2': last_high - 0.382 * diff,
            'fib_50.0': last_high - 0.500 * diff,
            'fib_61.8': last_high - 0.618 * diff,
            'fib_78.6': last_high - 0.786 * diff,
            'fib_100': last_high
        }

        for key, val in levels.items():
            self.df[key] = val
        return self

    def calculate_bollinger(self, latest_only=False, period=20, num_std=2):
        close = self.df['close_price']
        self.df['boll_sma'] = close.rolling(window=period).mean()
        self.df['boll_std'] = close.rolling(window=period).std()
        self.df['boll_upper'] = self.df['boll_sma'] + num_std * self.df['boll_std']
        self.df['boll_lower'] = self.df['boll_sma'] - num_std * self.df['boll_std']
        return self

    def calculate_rsi(self, latest_only=False, period=14):
        delta = self.df['close_price'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        self.df['rsi'] = 100 - (100 / (1 + rs))
        return self

    def calculate_macd(self, latest_only=False, fast=12, slow=26, signal=9):
        ema_fast = self.df['close_price'].ewm(span=fast).mean()
        ema_slow = self.df['close_price'].ewm(span=slow).mean()
        self.df['macd'] = ema_fast - ema_slow
        self.df['macd_signal'] = self.df['macd'].ewm(span=signal).mean()
        self.df['macd_hist'] = self.df['macd'] - self.df['macd_signal']
        return self

    def detect_candlestick_patterns(self, latest_only=False):
        df = self.df
        df['bullish_candle'] = df['close_price'] > df['open_price']
        df['bearish_candle'] = df['close_price'] < df['open_price']
        df['body'] = abs(df['close_price'] - df['open_price'])
        df['range'] = df['high_price'] - df['low_price']
        df['upper_shadow'] = df['high_price'] - df[['close_price', 'open_price']].max(axis=1)
        df['lower_shadow'] = df[['close_price', 'open_price']].min(axis=1) - df['low_price']
        df['doji'] = df['body'] <= (df['range'] * 0.1)
        df['hammer'] = (df['lower_shadow'] > 2 * df['body']) & (df['upper_shadow'] < df['body']) & df['bullish_candle']
        df['inv_hammer'] = (df['upper_shadow'] > 2 * df['body']) & (df['lower_shadow'] < df['body']) & df['bullish_candle']
        df['bullish_engulfing'] = (
            df['bullish_candle'] &
            (df['open_price'] < df['close_price'].shift(1)) &
            (df['close_price'] > df['open_price'].shift(1)) &
            df['bearish_candle'].shift(1)
        )
        df['bearish_engulfing'] = (
            df['bearish_candle'] &
            (df['open_price'] > df['close_price'].shift(1)) &
            (df['close_price'] < df['open_price'].shift(1)) &
            df['bullish_candle'].shift(1)
        )
        df['bullish_score'] = df[['hammer', 'inv_hammer', 'bullish_engulfing']].sum(axis=1)
        df['bearish_score'] = df[['bearish_engulfing']].sum(axis=1)

        def classify(row):
            if row['doji']:
                return "Neutral"
            if row['bullish_score'] > row['bearish_score']:
                return "Bullish"
            elif row['bearish_score'] > row['bullish_score']:
                return "Bearish"
            else:
                return "Neutral"

        df['patterns_result'] = df.apply(classify, axis=1)
        return self

    def get_df(self):
        return self.df
