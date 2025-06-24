import json
import logging
import traceback
import ccxt
import requests
from datetime import datetime

from app.viewmodels.api.kraken.KrakenAPI import KrakenAPI
from app.viewmodels.services.GenerateApiSign import GenerateApiSign

logger = logging.getLogger(__name__)
class KrakenAPISpot(KrakenAPI):
  def __init__(self, user_id):
    super().__init__(user_id, "spot", "https://api.kraken.com")
    self._add_order_endpoint = f"{self._base_url}/0/private/AddOrder"
    self.exchange = ccxt.kraken({
    'apiKey': "bicKNixp4Z2J0bsHNeCC51Uc4LBQFVFlJEr207gunl8WrXNM3XjQAQK2",
    'secret': "GtoFSj+iM+XTK6rd9BL5LR40eoyDord8/Y3Q9Vpjl3XCZuBg1ZODWPYLxqXHaacJbx19iXEaIhY/LEf1mrpGLA==",
})

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
    
  def add_order(self, order_type, order_direction, volume, symbol, price=0, order_made_by="user", money_wanted_to_spend=None):
        try:
            if order_made_by not in ["bot", "user"]:
                return {"error": ["order_made_by must be either 'bot' or 'user'"]}, 400
            
            # format symbol
            # find usd starting index
            """ usd_index = symbol.find("USD")
            if usd_index == -1:
                return {"error": ["Invalid symbol"]}, 400
            
            # add / before usd
            symbol = symbol[:usd_index] + "/" + symbol[usd_index:] """
            
            endpoint = "/0/private/AddOrder"
            full_url = self._base_url + endpoint
            nonce = self.get_nonce()

            if price == 0:
                # get price from kraken
                price, _ = self.get_symbol_price(symbol)
                if price.get("error"):
                    return price, 404
                else:
                    price = price["price"]

            if money_wanted_to_spend:
                # calculate volume
                volume = float(money_wanted_to_spend) / price

            stop_loss = self.calculate_stop_loss(price) # TODO: implement stop loss
            take_profit = self.calculate_take_profit(price) # TODO: implement take profit
            
    
            arguments = {
                "nonce": nonce,
                "ordertype": "market",
                "type": order_direction,
                "pair": symbol,
                "volume": volume,
                "price": price,
            }

            body = json.dumps(arguments)
            logger.info(f"🤑 Placing order: {json.dumps(arguments, indent=4)}")
            headers = {
                "Content-Type": "application/json",
                "API-Key": self._api_key,
                "API-Sign": self.get_signature(body, nonce, endpoint),
            }
            # logger.info(f"😀 Sending request to {full_url} \n with body {body}")
            response = requests.request("POST", full_url, data=body, headers=headers)
            data = response.json()
            
            if data["error"]:
                return {"error": data["error"] }, 400
            
            result = data["result"] 
            
            order_to_save = {
              "order_type": order_type,
              "order_direction": order_direction,
              "volume": volume,
              "symbol": symbol,
              "price": price,
              "by": order_made_by,
              "order_close_condition": result.get("descr").get("close"),
              "order_description": result.get("descr").get("order"),
              "order_id": result.get("txid")[0],
              "user_id": self.user_id,
              "stop_loss": stop_loss,
              "take_profit": take_profit,
              "exchange": "kraken",
            }

            order_saved = self.add_order_to_db(order_to_save)
            if not order_saved:
                return {"error": "Error saving order to database"}, 500            
            return order_saved, 200
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
      
    
  def fetch_ohlcv_optimized(self, symbol, timeframe, limit=5):
        """
        Obtiene las últimas 'limit' velas OHLCV para un símbolo y timeframe dado,
        optimizando el número de velas para el LLM.
        """
        try:
            # ccxt devuelve una lista de listas: [[timestamp, open, high, low, close, volume], ...]
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            # Formatear las velas para el LLM
            formatted_candles = []
            for candle in ohlcv:
                timestamp_ms = candle[0]
                open_price = round(candle[1], 4) # Redondea para optimizar espacio
                high_price = round(candle[2], 4)
                low_price = round(candle[3], 4)
                close_price = round(candle[4], 4)
                volume = round(candle[5], 2) # Redondea el volumen también

                # Convierte el timestamp a formato legible (opcional, puedes mantenerlo en ms si prefieres)
                dt_object = datetime.fromtimestamp(timestamp_ms / 1000)
                
                formatted_candles.append({
                    "timestamp": dt_object.strftime('%Y-%m-%d %H:%M:%S'),
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume
                })
            
            return formatted_candles
        except Exception as e:
            print(f"Error al obtener OHLCV para {symbol} {timeframe}: {e}")
            return []

  def get_market_context_for_llm(self, symbol, timeframes_to_monitor):
        """
        Prepara el contexto del mercado para el LLM, obteniendo solo las últimas N velas
        para cada timeframe especificado, optimizado para el espacio.
        
        Args:
            symbol (str): Par de trading (ej. 'BTC/USDT').
            timeframes_to_monitor (list): Lista de timeframes a considerar (ej. ['1m', '5m', '1h', '1d']).
                                        El usuario proporcionará el timeframe deseado aquí.
        Returns:
            dict: Un diccionario con el contexto del mercado, donde cada clave es un timeframe
                y el valor es una lista de las últimas velas.
        """
        market_context = {}
        for tf in timeframes_to_monitor:
            # Define un 'limit' razonable para cada timeframe.
            # Por ejemplo, las últimas 3-5 velas suelen ser suficientes para un contexto inmediato
            # sin sobrecargar el LLM.
            limit = 5 # Por defecto, obtenemos las últimas 5 velas. Puedes ajustar esto.
            
            # Podrías hacer el límite dinámico si quieres, pero para optimizar el espacio,
            # un número bajo y fijo como 3 o 5 es lo mejor.
            # if tf == '1m':
            #     limit = 5
            # elif tf == '1h':
            #     limit = 3
            # elif tf == '1d':
            #     limit = 2 # Solo la vela actual y la anterior

            candles = self.fetch_ohlcv_optimized(symbol, tf, limit=limit)
            
            if candles:
                market_context[tf] = candles
            else:
                market_context[tf] = {"error": "No se pudieron obtener datos"}

        return market_context
      
 
