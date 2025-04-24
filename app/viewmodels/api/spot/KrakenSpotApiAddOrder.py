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

        # Genera un nonce único (por ejemplo, usando el timestamp actual)
        nonce = int(time.time() * 1000)

        # Automatiza la generación de cl_ord_id
        cl_ord_id = str(uuid.uuid4())

        # Construir el diccionario de datos
        postdata = {
            "nonce": nonce,
            "ordertype": ordertype,
            "type": order_type,
            "volume": volume,
            "pair": symbol,
            "price": price,
            "cl_ord_id": cl_ord_id
        }

        # Calcula el API-Sign usando el método helper
        url_path = "/0/private/AddOrder"

        generate_api_sign = GenerateApiSign()  # Instanciar la clase GenerateApiSign
        api_sign = generate_api_sign.generate_api_sign(url_path, postdata, api_secret)

        # Prepara el payload y las cabeceras
        payload = json.dumps(postdata)
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'API-Key': api_key,
            'API-Sign': api_sign
        }

        try:
            response = requests.post(self.__endpoint, headers=headers, data=payload)
            if response.status_code != 200:
                logger.error(f"Error en la petición: HTTP {response.status_code}")
                return jsonify({"error": "Error en la petición"}), 500
            self.data = response.json()
            if "error" in self.data and self.data["error"]:
                logger.error(f"Error en la API de Kraken: {self.data['error']}")
                return {"error": str(self.data["error"])}, 500
            return self.data

        except Exception as e:
            logger.error(f"Error al enviar la orden: {e}")
            return {"error": str(e)}, 500
