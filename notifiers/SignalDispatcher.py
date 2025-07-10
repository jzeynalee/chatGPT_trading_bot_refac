class SignalDispatcher:
    def __init__(self, telegram_bot=None, linkedin_bot=None, twitter_bot=None):
        self.telegram_bot = telegram_bot
        self.linkedin_bot = linkedin_bot
        self.twitter_bot = twitter_bot

    def format_message(self, symbol, tf, row):
        msg = (
            f"🔔 Signal Alert\n"
            f"Symbol: {symbol.upper()}\n"
            f"Timeframe: {tf}\n"
            f"Direction: {'LONG' if row['signal_type'] == 'long' else 'SHORT'}\n"
            f"Price: {row['close_price']:.2f}\n"
            f"RSI: {row['rsi']:.1f}\n"
            f"#Crypto #Trading #Signals"
        )
        return msg

    def dispatch(self, strategy_results):
        for symbol, signals_by_tf in strategy_results:
            for tf, df in signals_by_tf.items():
                for _, row in df.iterrows():
                    msg = self.format_message(symbol, tf, row)
                    self._send_to_all(msg)

    def _send_to_all(self, message):
        if self.telegram_bot:
            self.telegram_bot.send_message(message)
        if self.linkedin_bot:
            self.linkedin_bot.send_post(message)
        if self.twitter_bot:
            self.twitter_bot.tweet(message)
