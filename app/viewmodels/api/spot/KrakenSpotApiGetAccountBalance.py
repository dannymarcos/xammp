import requests
import json, time
from flask import jsonify
from app.viewmodels.services.GenerateApiSign import GenerateApiSign  # Importar la clase GenerateApiSign
import random
import logging
import os
import threading

logger = logging.getLogger(__name__)

class KrakenSpotApiGetAccountBalance:
    # Lock for thread safety when accessing the nonce file
    _nonce_lock = threading.Lock()
    # Path to the file that stores the last used nonce
    _nonce_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kraken_last_nonce.txt')
    
    def __init__(self):
        self.__endpoint = "https://api.kraken.com/0/private/Balance"
        self.data = None
        
    @classmethod
    def _read_last_nonce(cls):
        """Read the last used nonce from the file"""
        try:
            with cls._nonce_lock:
                if os.path.exists(cls._nonce_file):
                    with open(cls._nonce_file, 'r') as f:
                        return int(f.read().strip())
                else:
                    # If file doesn't exist, return current time in milliseconds
                    return int(time.time() * 1000)
        except Exception as e:
            logger.error(f"Error reading nonce file: {e}")
            # Fallback to current time in milliseconds
            return int(time.time() * 1000)
    
    @classmethod
    def _write_nonce(cls, nonce):
        """Write the nonce to the file"""
        try:
            with cls._nonce_lock:
                with open(cls._nonce_file, 'w') as f:
                    f.write(str(nonce))
        except Exception as e:
            logger.error(f"Error writing to nonce file: {e}")

    def get_account_balance(self, api_key, api_secret):

        # Leer el último nonce utilizado
        last_nonce = self._read_last_nonce()
        
        # Generar un nonce único que sea siempre creciente
        current_nonce = int(time.time() * 1000)
        
        # Asegurar que el nonce sea mayor que el último utilizado
        if current_nonce <= last_nonce:
            current_nonce = last_nonce + 1 + random.randint(1, 1000)
        
        # Guardar el nuevo nonce
        self._write_nonce(current_nonce)
        
        # Convertir a string para la API
        nonce = str(current_nonce)
        
        logger.info(f"Using nonce: {nonce} (previous: {last_nonce})")

        #Construir el directorio de datos
        payload = {
            "nonce": nonce
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
