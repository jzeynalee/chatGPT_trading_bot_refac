class strategyEngine:
    def __init__(self, multi_df):
        """
        multi_df = {
            'HHT': df_4h,
            'HTF': df_1h,
            'TTF': df_15min,
            'LTF': df_5min,
            'LLT': df_1min
        }
        """
        self.multi_df = multi_df

    def get_df(self, tf):
        return self.multi_df.get(tf)

    # --- مشترک‌ها ---
    def is_bullish_kumo(self, tf):
        df = self.get_df(tf)
        if df is None: return False
        return df['senkou_span_a'].iloc[-1] > df['senkou_span_b'].iloc[-1]

    def is_bearish_kumo(self, tf):
        df = self.get_df(tf)
        if df is None: return False
        return df['senkou_span_a'].iloc[-1] < df['senkou_span_b'].iloc[-1]

    def chikou_above_price(self, tf):
        df = self.get_df(tf)
        if df is None: return False
        return df['chikou_span'].iloc[-1] > df['close_price'].iloc[-1]

    def chikou_below_price(self, tf):
        df = self.get_df(tf)
        if df is None: return False
        return df['chikou_span'].iloc[-1] < df['close_price'].iloc[-1]

    def is_tenkan_kijun_cross_up(self, tf):
        df = self.get_df(tf)
        if df is None or len(df) < 2: return False
        return df['tenkan_sen'].iloc[-1] > df['kijun_sen'].iloc[-1] and \
               df['tenkan_sen'].iloc[-2] <= df['kijun_sen'].iloc[-2]

    def is_tenkan_kijun_cross_down(self, tf):
        df = self.get_df(tf)
        if df is None or len(df) < 2: return False
        return df['tenkan_sen'].iloc[-1] < df['kijun_sen'].iloc[-1] and \
               df['tenkan_sen'].iloc[-2] >= df['kijun_sen'].iloc[-2]

    def is_bullish_candle(self, tf):
        df = self.get_df(tf)
        if df is None: return False
        return df['patterns_result'].iloc[-1] == "Bullish"

    def is_bearish_candle(self, tf):
        df = self.get_df(tf)
        if df is None: return False
        return df['patterns_result'].iloc[-1] == "Bearish"

    def rsi_below(self, tf, threshold=40):
        df = self.get_df(tf)
        if df is None: return False
        return df['rsi'].iloc[-1] < threshold

    def rsi_above(self, tf, threshold=60):
        df = self.get_df(tf)
        if df is None: return False
        return df['rsi'].iloc[-1] > threshold

    def close_above_kijun(self, tf):
        df = self.get_df(tf)
        if df is None: return False
        return df['close_price'].iloc[-1] > df['kijun_sen'].iloc[-1]

    def close_below_kijun(self, tf):
        df = self.get_df(tf)
        if df is None: return False
        return df['close_price'].iloc[-1] < df['kijun_sen'].iloc[-1]

    # --- Buy Strategy ---
    def generate_signal(self):
        if not self.is_bullish_kumo('HHT'):
            return "NoTrend"

        if not (self.is_bullish_kumo('HTF') and self.chikou_above_price('HTF')):
            return "WeakTrend"

        if not (self.is_tenkan_kijun_cross_up('TTF') and self.is_bullish_candle('TTF') and self.rsi_below('TTF')):
            return "WeakSignal"

        if not self.close_above_kijun('LTF'):
            return "WaitLTF"

        if not self.is_bullish_candle('LLT'):
            return "WaitLLT"

        return "Buy"

    # --- Sell Strategy ---
    def generate_signal_sell(self):
        if not self.is_bearish_kumo('HHT'):
            return "NoTrend"

        if not (self.is_bearish_kumo('HTF') and self.chikou_below_price('HTF')):
            return "WeakTrend"

        if not (self.is_tenkan_kijun_cross_down('TTF') and self.is_bearish_candle('TTF') and self.rsi_above('TTF')):
            return "WeakSignal"

        if not self.close_below_kijun('LTF'):
            return "WaitLTF"

        if not self.is_bearish_candle('LLT'):
            return "WaitLLT"

        return "Sell"

class TradePlanner:
    def __init__(self, equity: float, max_risk_pct: float = 2.0, rr_ratio: float = 2.0):
        self.equity = equity
        self.max_risk_pct = max_risk_pct
        self.rr_ratio = rr_ratio
        self.drawdown_limit_pct = 20.0  # Stop trading if 20% capital lost
        self.max_drawdown = self.equity * (self.drawdown_limit_pct / 100)
        self.cumulative_loss = 0.0

    def calculate_trade_levels(self, entry: float, direction: str, atr: float = None, fixed_sl_pct: float = 1.0):
        """
        Calculate SL/TP based on entry price and direction.
        """
        if atr:
            sl_distance = atr
        else:
            sl_distance = entry * (fixed_sl_pct / 100)

        if direction.lower() == 'long':
            sl = entry - sl_distance
            tp = entry + sl_distance * self.rr_ratio
        else:  # short
            sl = entry + sl_distance
            tp = entry - sl_distance * self.rr_ratio

        return round(sl, 6), round(tp, 6)

    def calculate_position_size(self, entry: float, sl: float):
        """
        Determine position size based on risk amount.
        """
        risk_per_unit = abs(entry - sl)
        max_risk_amount = self.equity * (self.max_risk_pct / 100)

        if risk_per_unit == 0:
            return 0  # prevent division by zero

        position_size = max_risk_amount / risk_per_unit
        return round(position_size, 4)

    def update_drawdown(self, pnl: float):
        """
        Update drawdown and check if trading should pause.
        """
        if pnl < 0:
            self.cumulative_loss += abs(pnl)

        if self.cumulative_loss >= self.max_drawdown:
            print("⚠️ Drawdown limit reached! Stop trading.")
            return False
        return True

    def plan_trade(self, signal: dict, atr: float = None):
        """
        Given a signal dict, plan the trade with full SL/TP/size details.
        signal = {
            'symbol': 'btc_usdt',
            'entry': 31000,
            'direction': 'long' or 'short'
        }
        """
        entry = signal['entry']
        direction = signal['direction']
        sl, tp = self.calculate_trade_levels(entry, direction, atr)
        size = self.calculate_position_size(entry, sl)

        return {
            'symbol': signal['symbol'],
            'entry': entry,
            'direction': direction,
            'sl': sl,
            'tp': tp,
            'position_size': size,
            'rr': self.rr_ratio
        }
