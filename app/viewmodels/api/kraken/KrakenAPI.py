import json

import requests
import logging

import time
import hashlib
import hmac
import base64

from app.viewmodels.services.GenerateApiSign import GenerateApiSign
from app.lib.settings import settings
import requests
import hashlib
import hmac
import base64
import time
import json
import traceback
from pydantic import BaseModel
from app.models.trades import Trade
from app.models.create_db import db



logger = logging.getLogger(__name__)

class TradingData(BaseModel):
    order_type: str
    order_direction: str
    volume: float
    symbol: str
    price: float



class KrakenAPI:
    def __init__(self, user_id, trading_mode = "spot", base_url = "https://api.kraken.com"):
        self.user_id = user_id
        self._base_url = base_url
        self._api_key = settings.KRAKEN_API_KEY
        self._api_secret = settings.KRAKEN_API_SECRET
        self.trading_mode = trading_mode
        self._add_order_endpoint = f"{self._base_url}/0/private/AddOrder"

    def get_creds_from_user(self, user_id):
        # TODO: implement
        pass
    
    def set_trading_mode(self, trading_mode):
        self.trading_mode = trading_mode

    def add_order_to_db(self, order):
        from main import app_instance

        app = app_instance
        try:
            if hasattr(app, 'app_context'):
                with app.app_context():
                    trade = Trade(**order)
                    db.session.add(trade)
                    db.session.commit()
                    return trade.serialize
            else:
                try:
                    trade = Trade(**order)
                    db.session.add(trade)
                    db.session.commit()
                    return trade.serialize
                except RuntimeError as e:
                    if 'working outside of application context' in str(e).lower():
                        raise RuntimeError("Flask application context not available")
                    raise
        except Exception as e:
            traceback.print_exc()
            return {"error": str(e)}, 400

    def calculate_stop_loss(self,target_price, stop_loss_percentage=0.02):
        return target_price * (1 - stop_loss_percentage)
    
    def calculate_take_profit(self,target_price, take_profit_percentage=0.04):
        return target_price * (1 + take_profit_percentage)

    def get_trades_history(self):
        raise NotImplementedError("Method not implemented")

    def add_order(self, order_type, order_direction, volume, symbol, price):
        raise NotImplementedError("Method not implemented")

    def get_symbol_price(self, symbol):
        try:
            # Use the provided symbol parameter in the URL
            url = f"https://api.kraken.com/0/public/Ticker?pair={symbol}"
            
            payload = {}
            headers = {
                'Accept': 'application/json'
            }

            response = requests.request("GET", url, headers=headers, data=payload)
            
            data = response.json()
            if data.get("error") and data["error"]:
                logger.error(f"Kraken API error: {data['error']}")
                return {"error": data["error"]}, 400
            
            # The result key in the response contains the ticker data
            # The key might be the symbol or a variation of it
            result_keys = list(data.get("result", {}).keys())
            if not result_keys:
                logger.error(f"No result keys found in response: {data}")
                return {"error": "No ticker data found for symbol"}, 404
            
            # Use the first key in the result (should be the requested symbol)
            ticker_key = result_keys[0]
            
            # 'a' is the ask array, 'b' is the bid array, 'c' is the last trade closed array
            # We'll use 'c' (last trade closed) as it's most commonly used for "current price"
            section = "c"  # Last trade closed
            position = 0   # Price is the first element in the array
            
            price = float(data["result"][ticker_key][section][position])
            
            return {"price": price}, 200
        except Exception as e:
            traceback.print_exc()
            return {"error": str(e)}, 400

    def get_nonce(self) -> str:
        return str(int(time.time() * 1000))

    def sign(self, message: bytes) -> str:
        return base64.b64encode(
            hmac.new(
                key=base64.b64decode(self._api_secret),
                msg=message,
                digestmod=hashlib.sha512,
            ).digest()
        ).decode()

    def get_signature(self,data: str, nonce: str, path: str) -> str:
        return self.sign(
            path.encode() + hashlib.sha256(
                    (nonce + data)
                .encode()
            ).digest()
        )
