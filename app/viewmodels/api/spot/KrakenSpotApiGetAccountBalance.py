import requests
import json, time
from flask import jsonify
from app.viewmodels.services.GenerateApiSign import GenerateApiSign  # Importar la clase GenerateApiSign

import logging

logger = logging.getLogger(__name__)

class KrakenSpotApiGetAccountBalance:
    def __init__(self):
        self.__endpoint = "https://api.kraken.com/0/private/Balance"
        self.data = None

    def get_account_balance(self, api_key, api_secret):

        #Generar un nonce único (por ejemplo, usando el timestamp actual)
        nonce = int(time.time()*1000)

        #Construir el directorio de datos
        payload = {
            "nonce":nonce
        }

        # Generar el API-Sign
        url_path = "/0/private/Balance"  # Ruta de la API

        generate_api_sign = GenerateApiSign()  # Instanciar la clase GenerateApiSign

        api_sign = generate_api_sign.generate_api_sign(url_path, payload, api_secret)

    
        # Depurar la solicitud
        # logger.info(f"API Key: {api_key}")
        # logger.info(f"API secret: {api_secret}")
        # logger.info(f"API Sign: {api_sign}")
        # logger.info(f"endpoint_url: {self.__endpoint}")
        # logger.info(f"Payload: {payload}")



        headers = {
            'API-Key': api_key,
            'API-Sign': api_sign
        }

        try:
            response = requests.post(self.__endpoint, headers=headers, data=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"Error en la petición: HTTP {response.status_code}")
                return jsonify({"error": "Error en la petición"}), 500
            
            # logger.info(f"response: {response}")
            # logger.info(f"response: {response.json()}")

            # Procesar la respuesta
            self.data = response.json()
            if "error" in self.data and self.data["error"]:
                logger.error(f"Error en la API de Kraken: {self.data['error']}")
                return {"error": str(self.data["error"])}, 500
            
            logger.info(f"data: {self.data}")
            # Devolver el balance
            return self.data

        except Exception as e:
            logger.error(f"Error al enviar la orden: {e}")
            return {"error": str(e)}, 500