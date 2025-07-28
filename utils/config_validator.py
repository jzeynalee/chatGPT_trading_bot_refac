def validate_config(config: dict):
    required_keys = [
        "WEBSOCKET_TIMEFRAME_CODES",
        "SYMBOLS",
        "TIMEFRAMES",
        "REST_TIMEFRAME_CODES",
        "LBANK_API"
    ]

    missing = [k for k in required_keys if k not in config or not config[k]]
    if missing:
        raise ValueError(f"Missing required configuration keys: {missing}")

    if not isinstance(config["SYMBOLS"], list) or not config["SYMBOLS"]:
        raise TypeError("SYMBOLS must be a non-empty list.")

    if not isinstance(config["TIMEFRAMES"], list) or not config["TIMEFRAMES"]:
        raise TypeError("TIMEFRAMES must be a non-empty list.")

    if not isinstance(config["WEBSOCKET_TIMEFRAME_CODES"], dict):
        raise TypeError("WEBSOCKET_TIMEFRAME_CODES must be a dictionary.")

    if not isinstance(config["REST_TIMEFRAME_CODES"], dict):
        raise TypeError("REST_TIMEFRAME_CODES must be a dictionary.")
