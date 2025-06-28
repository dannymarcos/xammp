"""Module for KrakenExchange API integration."""

import base64
import hashlib
import hmac
import logging
import os
import threading
import time
import traceback

import requests
from pydantic import BaseModel

from flask import current_app
from app.config import config
from app.models.create_db import db
from app.models.trades import Trade
from app.viewmodels.api.exchange.FatherExchange import Exchange

logger = logging.getLogger(__name__)

class TradingData(BaseModel):
    """
    Trading data
    """

    order_type: str
    order_direction: str
    volume: float
    symbol: str
    price: float

class KrakenExchange(Exchange):
    """
    Implementación concreta de la API de Kraken que hereda de Exchange.

    Attributes:
        _nonce_lock (threading.Lock): Lock para seguridad en hilos.
        _nonce_file_path (str): Ruta al archivo de almacenamiento de nonce.
        _base_url (str): URL base de la API de Kraken.
        _api_key (str): Clave API de Kraken.
        _api_secret (str): Secreto API de Kraken.
        _add_order_endpoint (str): Endpoint para añadir órdenes.
        _nonce_file (str): Ruta completa al archivo de nonce.
    """
    # Lock for thread safety when accessing the nonce file
    _nonce_lock = threading.Lock()
    # Path to the file that stores the last used nonce for this base class instance
    # Using a different file name to avoid conflict with the specific spot implementation's file
    _nonce_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kraken_base_nonce.txt')

    def __init__(self, user_id = 0, trading_mode = "spot", base_url = "https://api.kraken.com"):
        super().__init__(user_id, trading_mode)
        self.user_id = user_id
        self._base_url = base_url
        self._api_key = config.KRAKEN_API_KEY
        self._api_secret = config.KRAKEN_API_SECRET
        self.trading_mode = trading_mode
        self._add_order_endpoint = f"{self._base_url}/0/private/AddOrder"
        # Ensure nonce file path is instance-specific if needed, or manage centrally
        # For simplicity here, we use a single file defined at class level.
        # Consider if different instances (e.g., different users) need separate nonce files.
        self._nonce_file = KrakenExchange._nonce_file_path 

    def identification(self):
        return "Kraken"

    def get_creds_from_user(self, user_id):
        # TODO: implement
        pass

    def get_price(self, symbol):
        # Implementation here
        pass

    def set_trading_mode(self, trading_mode):
        self.trading_mode = trading_mode

    def calculate_stop_loss(self, target_price, stop_loss_percentage=0.02):
        return target_price * (1 - stop_loss_percentage)
    
    def calculate_take_profit(self, target_price, take_profit_percentage=0.04):
        return target_price * (1 + take_profit_percentage)

    def get_trades_history(self):
        raise NotImplementedError("Method not implemented")

    def add_order(
        self,
        order_direction,
        symbol,
        volume,
        order_type="market",
        order_made_by="bot",
        stop_loss=0,
        take_profit=0,
        leverage=1,
    ):
        raise NotImplementedError("Method not implemented")

    def get_symbol_price(self, symbol):
        try:
            # Use the provided symbol parameter in the URL
            url = f"https://api.kraken.com/0/public/Ticker?pair={symbol}"
            
            payload = {}
            headers = {
                'Accept': 'application/json'
            }

            response = requests.request("GET", url, headers=headers, data=payload, timeout=60)
            
            data = response.json()
            if data.get("error") and data["error"]:
                logger.error("Kraken API error: %s", data['error'])
                return {"error": data["error"]}, 400
            
            # The result key in the response contains the ticker data
            # The key might be the symbol or a variation of it
            result_keys = list(data.get("result", {}).keys())
            if not result_keys:
                logger.error("No result keys found in response: %s", data)
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
        """Reads the last nonce, calculates the next one, writes it back, and returns it."""
        # Use the instance's nonce file path
        nonce_file = self._nonce_file 
        with KrakenExchange._nonce_lock: # Use the class-level lock
            last_nonce = 0
            current_time_nonce = int(time.time() * 1_000_000) # Get current time early

            try:
                # Ensure file exists before reading
                if not os.path.exists(nonce_file):
                    # logger.info(f"Nonce file not found. Creating '{nonce_file}' with initial nonce.")
                    # Initialize file with a nonce slightly less than current time to ensure the first generated nonce is valid
                    initial_nonce = current_time_nonce - 1 
                    with open(nonce_file, encoding="utf-8", mode="w") as f:
                        f.write(str(initial_nonce))
                    last_nonce = initial_nonce
                else:
                    # Read the last nonce from the existing file
                    with open(nonce_file, encoding="utf-8", mode="r") as f:
                        content = f.read().strip()
                        if content:
                            try:
                                last_nonce = int(content)
                                logger.debug("Read last_nonce %s from file '%s'.", last_nonce, nonce_file)
                            except ValueError:
                                logger.error("Invalid content in nonce file '%s': '%s'. Using current time as fallback.", nonce_file, content)
                                last_nonce = current_time_nonce # Fallback if content is invalid
                        else:
                            # Handle empty file case - should ideally not happen with the creation logic above
                            logger.warning("Nonce file '%s' was empty. Initializing with current time.", nonce_file)
                            last_nonce = current_time_nonce # Fallback if file is empty
            except IOError as e:
                logger.error("IOError accessing nonce file '%s': %s", nonce_file, e)
                # Fallback to current time in microseconds if file access fails
                last_nonce = current_time_nonce
            except Exception as e:
                logger.error("Unexpected error handling nonce file '%s': %s", nonce_file, e)
                # Generic fallback
                last_nonce = current_time_nonce

            # Generate potential new nonce based on current time in microseconds
            # (current_time_nonce was already calculated)

            # Ensure the new nonce is strictly greater than the last one, increment by 2 for extra safety
            next_nonce = max(current_time_nonce, last_nonce + 2)

            # Write the new nonce back to the file
            try:
                with open(nonce_file, encoding="utf-8", mode="w") as f:
                    f.write(str(next_nonce))
            except Exception as e:
                logger.error("Error writing nonce %s to file '%s': %s", next_nonce, nonce_file, e)
                # If write fails, we still proceed with the calculated nonce,
                # but log the error. The next call might recover.

            logger.info("Generated nonce: %s (file: '%s', based on last: %s, current_time: %s)", next_nonce, nonce_file, last_nonce, current_time_nonce)
            return str(next_nonce) # Return as string for the API

    def sign(self, data: bytes) -> str:
        return base64.b64encode(
            hmac.new(
                key=base64.b64decode(self._api_secret),
                msg=data,
                digestmod=hashlib.sha512,
            ).digest()
        ).decode()

    def get_signature(self, data: str, nonce: str, path: str) -> str:
        return self.sign(
            path.encode() + hashlib.sha256(
                    (nonce + data)
                .encode()
            ).digest()
        )
    
    def get_account_balance(self):
        pass
    