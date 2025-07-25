# utils/timeframe.py
def normalize_tf(tf: str) -> str:
    """
    Map a bunch of aliases to a canonical key ('1h', '4h', ...).
    Extend if you add more.
    """
    t = tf.lower()
    aliases = {
        "1m": ["1m", "1min", "minute1"],
        "5m": ["5m", "5min", "minute5"],
        "15m": ["15m", "15min", "minute15"],
        "30m": ["30m", "30min", "minute30"],
        "1h": ["1h", "h1", "hour1"],
        "4h": ["4h", "h4", "hour4"],
        "8h": ["8h", "hour8"],
        "12h": ["12h", "hour12"],
        "1d": ["1d", "day1"],
        "1w": ["1w", "week1"],
        "1mth": ["1mth", "month1"],
    }
    for canon, alts in aliases.items():
        if t in alts:
            return canon
    return t
