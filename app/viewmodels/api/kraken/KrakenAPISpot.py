import json
import logging
import traceback

import requests

from app.viewmodels.api.kraken.KrakenAPI import KrakenAPI
from app.viewmodels.services.GenerateApiSign import GenerateApiSign

logger = logging.getLogger(__name__)
class KrakenAPISpot(KrakenAPI):
  def __init__(self, user_id):
    super().__init__(user_id, "spot", "https://api.kraken.com")
    self._add_order_endpoint = f"{self._base_url}/0/private/AddOrder"

  def get_account_balance(self):
    try:

      endpoint = "/0/private/Balance"
      full_url = f"{self._base_url}{endpoint}"
      
      nonce = self.get_nonce()
      payload = json.dumps({
        "nonce": self.get_nonce()
      })

      headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'API-Key': self._api_key,
        'API-Sign': self.get_signature(payload, nonce, endpoint)
      }

      response = requests.request("POST", full_url, headers=headers, data=payload)
      data = response.json()

      if data["error"]:
        return {"error": data["error"] }, 400
      
      return data, 200

    except Exception as e:
      logger.error(f"Error getting account balance: {e}")
      return {"error": str(e)}, 500
    
  def add_order(self, order_type, order_direction, volume, symbol, price):
        try:
            endpoint = "/0/private/AddOrder"
            full_url = self._base_url + endpoint
            nonce = self.get_nonce()

            volume = 10
            symbol = "USDTUSD"
            type = "buy"
            price = 0.99
            money_spent = float(volume) * float(price)
            print(f"money spent: {money_spent}")
            arguments = {
                "nonce": nonce,
                "ordertype": "market",
                "type": type,
                "pair": symbol,
                "volume": volume,
                "price": price,
            }
            body = json.dumps(arguments)
            print("A")
            headers = {
                "Content-Type": "application/json",
                "API-Key": self._api_key,
                "API-Sign": self.get_signature(body, nonce, endpoint),
            }
            logger.info(f"😀 Sending request to {full_url} \n with body {body}")
            response = requests.request("POST", full_url, data=body, headers=headers)
            data = response.json()

            print("AAAAAAA")
            print(data)
            
            if data["error"]:
                return {"error": data["error"] }, 400
                        
            return data, 200
        except Exception as e:
            traceback.print_exc()
            return {"error": str(e)}, 400


  def get_trades_history(self, type = "all", trades = False, consolidate_taker = True):
      try:
        url = "https://api.kraken.com/0/private/TradesHistory"
        nonce = self.get_nonce()
        payload = json.dumps({
          "nonce": nonce,
          "type": type,
          "trades": trades,
          "consolidate_taker": consolidate_taker
        })
        headers = {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'API-Key': self._api_key,
          'API-Sign': self.get_signature(payload, nonce, url)
        }

        response = requests.request("POST", url, headers=headers, data=payload)
        data = response.json()

        if data["error"]:
          return {"error": data["error"] }, 400
        
        return data, 200

      except Exception as e:
        logger.error(f"Error getting trades history: {e}")
        return {"error": str(e)}, 500
