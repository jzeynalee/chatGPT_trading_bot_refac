from typing import Any, Dict


class ConfigManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def get_ws_url(self) -> str:
        return (
            self.config.get("LBANK_API", {}).get("websocket_url")
            or self.config.get("WEBSOCKET_URL")
            or "wss://www.lbkex.net/ws/V2/"
        )

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def get_timeframe_mapping(self) -> Dict[str, str]:
        return (
            self.config.get("TIMEFRAME_MAPPING")
            or self.config.get("WEBSOCKET_TIMEFRAME_CODES", {})
            or {}
        )

    def get_rest_code_map(self) -> Dict[str, str]:
        return (
            self.config.get("rest_code_map")
            or self.config.get("REST_TIMEFRAME_CODES")
            or {}
        )

    def get_symbols(self) -> list:
        return self.config.get("symbols") or self.config.get("SYMBOLS") or []

    def get_timeframes(self) -> list:
        return self.config.get("timeframes") or self.config.get("TIMEFRAMES") or []

    def get_max_retries(self) -> int:
        return int(self.config.get("WS_MAX_RETRIES", 5))

    def get_depth_level(self) -> int:
        return int(self.config.get("DEPTH_LEVEL", 50))