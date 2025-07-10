import pandas as pd
from trader import Trader
from notifier import Notifier  # Assumed class that posts to socials
from datetime import datetime


class SignalChecker:
    def __init__(self, signal_file, trader: Trader, notifier: Notifier):
        self.signal_file = signal_file
        self.trader = trader
        self.notifier = notifier
        self.df = pd.read_csv(signal_file)

    def check_signals(self):
        for i, row in self.df.iterrows():
            if row['status'] != 'OPEN':
                continue  # already processed

            symbol = row['symbol']
            direction = row['direction']
            entry = row['entry']
            sl = row['sl']
            tp = row['tp']
            current_price = self.get_current_price(symbol)

            if current_price is None:
                continue

            hit_tp = (direction == "long" and current_price >= tp) or (direction == "short" and current_price <= tp)
            hit_sl = (direction == "long" and current_price <= sl) or (direction == "short" and current_price >= sl)

            if hit_tp:
                self.df.at[i, 'status'] = 'SUCCESS'
                msg = f"✅ Signal SUCCESS: {symbol} {direction.upper()} @ {entry}\n🎯 TP hit at {tp}"
                self.notifier.send(msg)
            elif hit_sl:
                self.df.at[i, 'status'] = 'FAILURE'
                msg = f"❌ Signal FAILED: {symbol} {direction.upper()} @ {entry}\n💥 SL hit at {sl}"
                self.notifier.send(msg)

        self.df.to_csv(self.signal_file, index=False)

    def get_current_price(self, symbol: str) -> float:
        try:
            url = f"https://api.lbank.info/v2/ticker.do?symbol={symbol}"
            response = requests.get(url).json()
            return float(response['ticker']['latest'])
        except Exception as e:
            print(f"Error getting price for {symbol}: {e}")
            return None
