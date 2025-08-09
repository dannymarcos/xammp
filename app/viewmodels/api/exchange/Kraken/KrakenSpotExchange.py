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
            'enableRateLimit': True,
            'sandbox': False,  # Set to True for testing
        })

        self.rateLimit = getattr(self.exchange, 'rateLimit', 2000)

    @property
    def rateLimit(self):
        return self._rateLimit
    
    @rateLimit.setter
    def rateLimit(self, value):
        self._rateLimit = max(value, 1000)

    def get_account_balance(self):
        try:
            balance = self.exchange.fetch_balance()
            balance_list = []

            # Filtrar solo las monedas con saldo positivo
            for currency, amount in balance['total'].items():
                if amount > 0:
                    balance_list.append(
                        {"currency": currency.upper(), "amount": float(amount)}
                    )
  
            return balance_list
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
        order_made_by="user"
    ):
        try:
            if order_made_by not in ["bot", "user"]:
                raise ValueError("order_made_by must be 'bot' or 'user'")

            # Validate inputs
            if not volume or volume <= 0:
                return None, "Volume must be greater than 0"
            
            if not symbol:
                return None, "Symbol is required"

            # Get current price if not provided
            if price == 0:
                price_data, status_code = self.get_symbol_price(symbol)
                if status_code == 200 and "price" in price_data:
                    price = price_data["price"]
                else:
                    return None, f"Failed to get current price: {price_data.get('error', 'Unknown error')}"

            if isinstance(price, dict) and "price" in price:
                price = price["price"]

            if price <= 0:
                return None, "Price must be greater than 0"

            logger.info("Placing spot order for %s - Volume: %s, Price: %s", symbol, volume, price)
            print({
                "symbol": symbol,
                "order_type": order_type,
                "order_direction": order_direction,
                "volume": volume,
                "price": price,
            })
            
            # Load markets to ensure symbol is available
            try:
                self.exchange.load_markets()
                if symbol not in self.exchange.markets:
                    return None, f"Symbol {symbol} not found in available markets"
            except Exception as market_error:
                logger.warning(f"Could not load markets: {market_error}")
                # Continue anyway as the order might still work
            
            # Execute order
            try:
                logger.info(f"Creating {order_type} order: {order_direction} {volume} {symbol} at {price}")
                
                if order_type == "limit":
                    order = self.exchange.create_order(
                        symbol=symbol,
                        type=order_type,
                        side=order_direction,
                        amount=volume,
                        price=price
                    )
                else:  # market order
                    order = self.exchange.create_order(
                        symbol=symbol,
                        type=order_type,
                        side=order_direction,
                        amount=volume
                    )
                
                logger.info(f"Order created successfully: {order}")
                
            except Exception as order_error:
                logger.error(f"Error creating order: {order_error}")
                logger.error(f"Order details: symbol={symbol}, type={order_type}, side={order_direction}, amount={volume}, price={price}")
                return None, f"Order creation failed: {str(order_error)}"

            print(f"Order created successfully: {order}")

            # Prepare order record
            order_record = {
                "order_type": order_type,
                "order_direction": order_direction,
                "volume": volume,
                "symbol": symbol,
                "price": price,
                "by": order_made_by,
                "order_id": order.get("id"),
                "user_id": self.user_id,
                "stop_loss": 0,  # Spot doesn't have native SL/TP
                "take_profit": 0,  # Handled externally
                "exchange": "kraken_spot",
                "trading_mode": "spot",
                "status": "open",
                "leverage": 1,
            }

            # Save to database
            if not self.add_order_to_db(order_record):
                logger.error("Failed to save spot order to database")
                return None, "Database save error"

            return order, None

        except Exception as e:
            logger.error(f"Spot order placement error: {e}")
            traceback.print_exc()
            return None, str(e)

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
    
    def get_kraken_order_details(self, order_id):
        result_template = {
            "symbol": None,
            "side": None,
            "filled": 0,
            "cost": 0,
            "fee": None,
            "fee_currency": None,
            "error": None
        }

        try:
            order = self.exchange.fetch_order(order_id)
            symbol = order['symbol']
            side = order['side']
            filled = float(order['filled'])
            cost = float(order['cost'])
            fee_data = order.get('fee', {})
            price = float(order.get("price"))
            
            original_fee = float(fee_data.get('cost', 0))
            original_fee_currency = fee_data.get('currency')

            fee = {}
            fee[original_fee_currency] = original_fee
            fee[symbol.split("/")[0]] = original_fee/price

            return {
                **result_template,
                "symbol": symbol,
                "side": side,
                "filled": filled,
                "cost": cost,
                "fee": fee,
            }

        except Exception as e:
            return {
                **result_template,
                "error": f"Error: {str(e)}"
            }