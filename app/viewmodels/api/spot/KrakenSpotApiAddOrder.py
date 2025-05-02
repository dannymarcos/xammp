import json
import uuid
import requests
import logging
from flask import jsonify
import time
import hashlib
import hmac
import base64
from app.viewmodels.services.GenerateApiSign import GenerateApiSign

logger = logging.getLogger(__name__)
import requests
import hashlib
import hmac
import base64
import time
import json


method = "POST"
environment_url = "https://api.kraken.com"
path = "/0/private/AddOrder"
public_key = ""
private_key = "PpeGj6z4uaxz2KNgIIdccC8cVQR+brTrLXUAEWsHhTw5TSMMZY5PBNFnEw+RkJaMlp2mHxfZMPYwemiGHs6eig=="


class KrakenSpotApiAddOrder:
    def __init__(self):
        self.__endpoint = "https://api.kraken.com/0/private/AddOrder"
        self.data = None

    def add_order(self, ordertype, order_type, volume, symbol, price, api_key, api_secret):
        """
        Envía una orden a Kraken.
        
        Parámetros:
          - ordertype: Tipo de orden (por ejemplo, 'limit', 'market', etc.)
          - order_type: Dirección de la orden ('buy' o 'sell')
          - volume: Volumen de la orden (en el activo base)
          - symbol: Par de trading (por ejemplo, 'XBTUSD')
          - price: Precio límite (si aplica)
          - api_key: Tu API key de Kraken.
          - api_secret: Tu API secret de Kraken.
        """
        nonce = self.get_nonce()
        arguments = {
            "nonce": nonce,
            "ordertype": "limit",
            "type": "buy",
            "pair": "BTC/USD",
            "volume": "1",
            "price": "1",
        }
        body = json.dumps(arguments)
        headers = {
            "Content-Type": "application/json",
            "API-Key": api_key,
            "API-Sign": self.get_signature(body, nonce, path),
        }
        response = requests.request(method, environment_url + path, data=body, headers=headers)
        print(response.text)

    def get_nonce(self) -> str:
        return str(int(time.time() * 1000))

    def sign(self, message: bytes) -> str:
        return base64.b64encode(
            hmac.new(
                key=base64.b64decode(private_key),
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
