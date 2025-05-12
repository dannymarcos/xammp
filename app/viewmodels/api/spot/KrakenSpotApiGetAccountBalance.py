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
    def _get_next_nonce(cls):
        """Reads the last nonce, calculates the next one, writes it back, and returns it."""
        with cls._nonce_lock:
            last_nonce = 0
            current_time_nonce = int(time.time() * 1_000_000) # Get current time early

            try:
                # Ensure file exists before reading
                if not os.path.exists(cls._nonce_file):
                    logger.debug(f"Nonce file not found. Creating '{cls._nonce_file}' with initial nonce.")
                    # Initialize file with a nonce slightly less than current time to ensure the first generated nonce is valid
                    initial_nonce = current_time_nonce - 1 
                    with open(cls._nonce_file, 'w') as f:
                        f.write(str(initial_nonce))
                    last_nonce = initial_nonce
                else:
                    # Read the last nonce from the existing file
                    with open(cls._nonce_file, 'r') as f:
                        content = f.read().strip()
                        if content:
                            try:
                                last_nonce = int(content)
                                # logger.debug(f"Read last_nonce {last_nonce} from file.")
                            except ValueError:
                                logger.error(f"Invalid content in nonce file: '{content}'. Using current time as fallback.")
                                last_nonce = current_time_nonce # Fallback if content is invalid
                        else:
                            # Handle empty file case - should ideally not happen with the creation logic above
                            # logger.warning("Nonce file was empty. Initializing with current time.")
                            last_nonce = current_time_nonce # Fallback if file is empty
            except IOError as e:
                logger.error(f"IOError accessing nonce file '{cls._nonce_file}': {e}")
                # Fallback to current time in microseconds if file access fails
                last_nonce = current_time_nonce
            except Exception as e:
                logger.error(f"Unexpected error handling nonce file: {e}")
                # Generic fallback
                last_nonce = current_time_nonce

            # Generate potential new nonce based on current time in microseconds
            # (current_time_nonce was already calculated)

            # Ensure the new nonce is strictly greater than the last one, increment by 2 for extra safety
            next_nonce = max(current_time_nonce, last_nonce + 2)

            # Write the new nonce back to the file
            try:
                with open(cls._nonce_file, 'w') as f:
                    f.write(str(next_nonce))
            except Exception as e:
                logger.error(f"Error writing nonce {next_nonce} to file: {e}")
                # If write fails, we still proceed with the calculated nonce,
                # but log the error. The next call might recover.

            logger.info(f"Generated nonce: {next_nonce} (based on last: {last_nonce}, current_time: {current_time_nonce})")
            return str(next_nonce) # Return as string for the API

    def get_account_balance(self, api_key, api_secret):
        # Generar el nonce único y creciente de forma atómica
        nonce = self._get_next_nonce()

        # Construir el directorio de datos
        payload = {
            "nonce": nonce
        }

        # Generar el API-Sign
        url_path = "/0/private/Balance"  # Ruta de la API
        generate_api_sign = GenerateApiSign()  # Instanciar la clase GenerateApiSign
        api_sign = generate_api_sign.generate_api_sign(url_path, payload, api_secret)

        headers = {
            'API-Key': api_key,
            'API-Sign': api_sign
        }

        try:
            response = requests.post(self.__endpoint, headers=headers, data=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"Error en la petición: HTTP {response.status_code}")
                # Return a dictionary instead of jsonify for consistency within the class method
                return {"error": f"Error en la petición HTTP {response.status_code}"}, response.status_code

            # Procesar la respuesta
            self.data = response.json()
            if "error" in self.data and self.data["error"]:
                logger.error(f"Error en la API de Kraken: {self.data['error']}")
                # Propagate Kraken's error message and potentially a 500 or specific error code if available
                return {"error": f"Kraken API Error: {self.data['error']}"}, 500 # Assuming 500 for API errors

            logger.info(f"Account balance data received: {self.data}")
            # Devolver el balance
            return self.data

        except requests.exceptions.Timeout:
            logger.error("Error al enviar la orden: Timeout")
            return {"error": "Request timed out"}, 504 # Gateway Timeout
        except requests.exceptions.RequestException as e:
            logger.error(f"Error al enviar la orden (RequestException): {e}")
            return {"error": f"Request failed: {e}"}, 500 # Internal Server Error for general request issues
        except Exception as e:
            logger.error(f"Error inesperado en get_account_balance: {e}")
            return {"error": f"An unexpected error occurred: {e}"}, 500
