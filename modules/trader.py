import time
import hmac
import hashlib
import requests
import urllib.parse


class Trader:
    def __init__(self, api_key: str, secret_key: str, base_url="https://api.lbank.info"):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url

    def _generate_signature(self, params: dict):
        params = dict(sorted(params.items()))
        encoded = urllib.parse.urlencode(params)
        to_sign = encoded + "&secret_key=" + self.secret_key
        sign = hashlib.md5(to_sign.encode()).hexdigest().upper()
        return sign

    def _private_post(self, endpoint: str, params: dict):
        url = self.base_url + endpoint
        params['api_key'] = self.api_key
        params['timestamp'] = int(time.time() * 1000)
        params['sign'] = self._generate_signature(params)
        response = requests.post(url, data=params)
        return response.json()

    def place_order(self, symbol: str, side: str, amount: float, price: float = None, order_type: str = "limit"):
        """
        side: 'buy' or 'sell'
        order_type: 'limit' or 'market'
        """
        endpoint = "/v2/create_order.do"

        params = {
            "symbol": symbol,
            "type": side + "_market" if order_type == "market" else side,
            "amount": str(amount)
        }

        if order_type == "limit":
            params["price"] = str(price)

        print(f"📤 Placing {order_type.upper()} {side.upper()} order: {amount} {symbol} @ {price or 'MARKET'}")
        return self._private_post(endpoint, params)

    def cancel_order(self, symbol: str, order_id: str):
        endpoint = "/v2/cancel_order.do"
        params = {
            "symbol": symbol,
            "order_id": order_id
        }
        return self._private_post(endpoint, params)

    def get_open_orders(self, symbol: str):
        endpoint = "/v2/orders_info_no_deal.do"
        params = {
            "symbol": symbol
        }
        return self._private_post(endpoint, params)

    def get_order_info(self, symbol: str, order_id: str):
        endpoint = "/v2/order_info.do"
        params = {
            "symbol": symbol,
            "order_id": order_id
        }
        return self._private_post(endpoint, params)

    def get_balance(self):
        endpoint = "/v2/user_info.do"
        params = {}
        return self._private_post(endpoint, params)
