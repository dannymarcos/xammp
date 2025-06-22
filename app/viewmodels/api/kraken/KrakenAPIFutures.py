import logging
import traceback
import ccxt
from app.viewmodels.api.kraken.KrakenAPI import KrakenAPI
logger = logging.getLogger(__name__)

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