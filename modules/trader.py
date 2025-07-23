# modules/trader.py
import time
import hashlib
import requests
import urllib.parse
from typing import Optional


class Trader:
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        base_url: str = "https://api.lbank.info",
        logger: Optional[object] = None,
    ):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        self.logger = logger

    def _generate_signature(self, params: dict) -> str:
        params = dict(sorted(params.items()))
        encoded = urllib.parse.urlencode(params)
        to_sign = encoded + "&secret_key=" + self.secret_key
        return hashlib.md5(to_sign.encode()).hexdigest().upper()

    def _private_post(self, endpoint: str, params: dict):
        url = self.base_url + endpoint
        params["api_key"] = self.api_key
        params["timestamp"] = int(time.time() * 1000)
        params["sign"] = self._generate_signature(params)
        resp = requests.post(url, data=params)
        data = resp.json()
        if self.logger:
            self.logger.debug("LBANK POST %s %s -> %s", endpoint, params, data)
        return data

    def place_order(self, symbol: str, side: str, amount: float, price: float = None, order_type: str = "limit"):
        """Place an order at LBank."""
        endpoint = "/v2/create_order.do"
        params = {
            "symbol": symbol,
            "type": side + "_market" if order_type == "market" else side,
            "amount": str(amount),
        }
        if order_type == "limit" and price is not None:
            params["price"] = str(price)

        if self.logger:
            self.logger.info("📤 Placing %s %s order: %s %s @ %s", order_type.upper(), side.upper(), amount, symbol, price or "MARKET")
        return self._private_post(endpoint, params)

    def cancel_order(self, symbol: str, order_id: str):
        return self._private_post("/v2/cancel_order.do", {"symbol": symbol, "order_id": order_id})

    def get_open_orders(self, symbol: str):
        return self._private_post("/v2/orders_info_no_deal.do", {"symbol": symbol})

    def get_order_info(self, symbol: str, order_id: str):
        return self._private_post("/v2/order_info.do", {"symbol": symbol, "order_id": order_id})

    def get_balance(self):
        return self._private_post("/v2/user_info.do", {})
