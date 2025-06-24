import logging
import traceback
import ccxt
from app.viewmodels.api.kraken.KrakenAPI import KrakenAPI
logger = logging.getLogger(__name__)
from datetime import datetime

class KrakenAPIFutures(KrakenAPI):
  def __init__(self, user_id):
    super().__init__( user_id, "futures", "https://futures.kraken.com")
    self.exchange = ccxt.krakenfutures({
    'apiKey': "1kWBgDCKap5OtPVWw0Yn5x3rseXrnyb0NZA0f3tgVEVo8FFcavqySGUN",
    'secret': "rDzCkSp+EVq1s03IvemM1GI//itRXO5OsH5IYedIKzijjs9FJp69AooBFXMN2ZI4OyO+7tGe1kWm4B+NxJnnhm/J",
})
    

  def get_account_balance(self):
        try:
            balance = self.exchange.fetch_free_balance()
            balance_list = []
            for currency, amount in balance.items():
                balance_list.append({"currency": currency, "amount": amount})
  
            return balance_list
        except Exception as e:
            return {"error": str(e)}
    

  def get_symbol_price(self, symbol: str):
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker["last"], 200
        except Exception as e:
            return {"error": str(e)}, 500

  def get_cryptos(self):
        tickers = self.exchange.fetch_tickers()
        symbols = [{"symbol": symbol, "price": data["last"]} for symbol, data in tickers.items()]
        return symbols, 200


  def close_order(self, symbol, side, params):
      print("🚀 Closing futures order for " + symbol)
      order = self.exchange.close_position(symbol, side, params)
      print(order )

  def add_order(self, order_type, order_direction, volume, symbol, price=None, leverage=1, take_profit=None, stop_loss=None, order_made_by="user"):
      try:
        print(f"🚀 Placing futures order for {symbol} with stop loss {stop_loss} and take profit {take_profit}")
        if order_made_by not in ["bot", "user"]:
            return {"error": ["order_made_by must be either 'bot' or 'user'"]}, 400

        params = {}
        if leverage:
            self.exchange.set_leverage(leverage, symbol)
            params["maxLeverage"] = leverage # not working
        if take_profit:
            params["takeProfitPrice"] = float(take_profit)
        if stop_loss:
            params["stopLossPrice"] = float(stop_loss)
        
        if order_direction == "buy":
            # order = self.exchange.create_market_buy_order(symbol, volume, params=params)
            order = self.exchange.add_order(symbol=symbol, side="buy", amount=volume, type="market", params=params)
        elif order_direction == "sell":
            #order = self.exchange.create_market_sell_order(symbol, volume, params=params)
            order = self.exchange.add_order(symbol=symbol, side="sell", amount=volume, type="market", params=params)

        else:
            return None, "Invalid order direction"
        import json
        print(json.dumps(order, indent=4))

        order_to_save = {
                "order_type": order_type,
                "order_direction": order_direction,
                "volume": volume,
                "symbol": symbol,
                "price": order.get("price"),
                "by": order_made_by,
                "order_id": order.get("id"),
                "user_id": self.user_id,
                "stop_loss": float(stop_loss) if stop_loss else 0,
                "take_profit": float(take_profit) if take_profit else 0,
                "exchange": "kraken-futures",
                }
        
        order_saved = self.add_order_to_db(order_to_save)
        if not order_saved:
            print("Error saving order to database")
            return None, "Error saving order to database"   

        self.exchange.set_leverage(1, symbol)
        return order, None
      except Exception as e:
        logger.error(f"😅 Error adding order: {e}")
        traceback.print_exc()
        return None, str(e)
      
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