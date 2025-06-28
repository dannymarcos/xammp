import json
import logging
import traceback
from datetime import datetime

import ccxt
import requests

from app.config import config
from app.viewmodels.api.exchange.Kraken.KrakenExchange import KrakenExchange

logger = logging.getLogger(__name__)

class KrakenSpotExchange(KrakenExchange):
    def __init__(self, user_id=0):
        super().__init__(user_id, "spot", "https://api.kraken.com")
        self._add_order_endpoint = f"{self._base_url}/0/private/AddOrder"
        self.exchange = ccxt.kraken({
            'apiKey': config.KRAKEN_SPOT_API_KEY,
            'secret': config.KRAKEN_SPOT_API_SECRET,
        })

    def get_account_balance(self):
        try:
            endpoint = "/0/private/Balance"
            full_url = f"{self._base_url}{endpoint}"
            nonce = self.get_nonce()
            
            payload = json.dumps({
                "nonce": nonce
            })
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'API-Key': self._api_key,
                'API-Sign': self.get_signature(payload, nonce, endpoint)
            }

            response = requests.post(full_url, headers=headers, data=payload)
            data = response.json()

            if data["error"]:
                return {"error": data["error"]}, 400
            
            return data, 200

        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            return {"error": str(e)}, 500

    def add_order(
        self,
        order_type,
        order_direction,
        volume,
        symbol,
        price=0,
        order_made_by="user",
        money_wanted_to_spend=None
    ):
        try:
            if order_made_by not in ["bot", "user"]:
                return {
                    "error": ["order_made_by must be either 'bot' or 'user'"]
                }, 400
            
            endpoint = "/0/private/AddOrder"
            full_url = self._base_url + endpoint
            nonce = self.get_nonce()

            # Obtener precio si no se proporciona
            if price == 0:
                price_data, _ = self.get_symbol_price(symbol)
                if price_data.get("error"):
                    return price_data, 404
                price = price_data["price"]

            # Calcular volumen si se especifica el monto a gastar
            if money_wanted_to_spend:
                volume = float(money_wanted_to_spend) / price

            stop_loss = self.calculate_stop_loss(price)
            take_profit = self.calculate_take_profit(price)
            
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
            
            response = requests.post(full_url, data=body, headers=headers)
            data = response.json()
            
            if data["error"]:
                return {"error": data["error"]}, 400
            
            result = data["result"]
            order_to_save = {
                "order_type": order_type,
                "order_direction": order_direction,
                "volume": volume,
                "symbol": symbol,
                "price": price,
                "by": order_made_by,
                "order_close_condition": result["descr"]["close"],
                "order_description": result["descr"]["order"],
                "order_id": result["txid"][0],
                "user_id": self.user_id,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "exchange": "kraken",
            }

            if not self.add_order_to_db(order_to_save):
                return {"error": "Error saving order to database"}, 500
            
            return order_to_save, 200
        
        except Exception as e:
            traceback.print_exc()
            return {"error": str(e)}, 400

    def get_trades_history(self, trade_type="all", trades=False, consolidate_taker=True):
        try:
            url = f"{self._base_url}/0/private/TradesHistory"
            nonce = self.get_nonce()
            payload = json.dumps({
                "nonce": nonce,
                "type": trade_type,
                "trades": trades,
                "consolidate_taker": consolidate_taker
            })
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'API-Key': self._api_key,
                'API-Sign': self.get_signature(payload, nonce, "/0/private/TradesHistory")
            }

            response = requests.post(url, headers=headers, data=payload)
            data = response.json()

            if data["error"]:
                return {"error": data["error"]}, 400
            
            return data, 200

        except Exception as e:
            logger.error(f"Error getting trades history: {e}")
            return {"error": str(e)}, 500

    def fetch_ohlcv_optimized(self, symbol, timeframe, limit=5):
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            formatted_candles = []
            
            for candle in ohlcv:
                timestamp_ms = candle[0]
                dt_object = datetime.fromtimestamp(timestamp_ms / 1000)
                
                formatted_candles.append({
                    "timestamp": dt_object.strftime('%Y-%m-%d %H:%M:%S'),
                    "open": round(candle[1], 4),
                    "high": round(candle[2], 4),
                    "low": round(candle[3], 4),
                    "close": round(candle[4], 4),
                    "volume": round(candle[5], 2)
                })
            
            return formatted_candles
        
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol} {timeframe}: {e}")
            return []

    def get_market_context_for_llm(self, symbol, timeframes_to_monitor):
        market_context = {}
        for tf in timeframes_to_monitor:
            try:
                candles = self.fetch_ohlcv_optimized(symbol, tf, limit=5)
                market_context[tf] = candles
            except Exception as e:
                market_context[tf] = {"error": f"Failed to get data: {str(e)}"}
        
        return market_context