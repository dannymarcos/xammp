import json
import logging
import traceback
from datetime import datetime

import ccxt
from app.config import config

from app.viewmodels.api.exchange.Kraken.KrakenExchange import KrakenExchange

logger = logging.getLogger(__name__)

# Este seria el equivalente al KrakenAPIFutures que se tenia anteriormente
class KrakenFuturesExchange(KrakenExchange):
    """Handles futures trading operations for Kraken exchange."""

    def __init__(self, user_id = 0):
        super().__init__(user_id, "futures", "https://futures.kraken.com")
        
        self.exchange = ccxt.krakenfutures({
            'apiKey': config.KRAKEN_FUTURE_API_KEY,
            'secret': config.KRAKEN_FUTURE_API_SECRET,
        })

        self.rateLimit = getattr(self.exchange, 'rateLimit', 2000)

    @property
    def rateLimit(self):
        return self._rateLimit
    
    @rateLimit.setter
    def rateLimit(self, value):
        self._rateLimit = max(value, 1000)

    def get_account_balance(self):
        """Retrieve account balance."""
        try:
            balance = self.exchange.fetch_free_balance()
            return [
                {"currency": currency, "amount": amount}
                for currency, amount in balance.items()
            ]
        except Exception as e:
            logger.error("Balance error: %s", e)
            return {"error": str(e)}

    def get_symbol_price(self, symbol: str):
        """Get current price for a trading symbol."""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker["last"], None
        except Exception as e:
            logger.error("Price error for %s: %s", symbol, e)
            return None, str(e)

    def get_cryptos(self):
        """Retrieve all available cryptocurrencies."""
        try:
            tickers = self.exchange.fetch_tickers()
            return [
                {"symbol": symbol, "price": data["last"]}
                for symbol, data in tickers.items()
            ], 200
        except Exception as e:
            logger.error("Crypto data error: %s", e)
            return {"error": str(e)}, 500

    def close_order(self, symbol, side, params):
        """Close a futures position."""
        logger.info("Closing futures order for %s", symbol)
        try:
            order = self.exchange.close_position(symbol, side, params)
            logger.info("Order closed: %s", order)
            return order
        except Exception as e:
            logger.error("Close order error: %s", e)
            return None

    def add_order(
        self,
        order_type,
        order_direction,
        volume,
        symbol,
        leverage=1,
        take_profit=None,
        stop_loss=None,
        order_made_by="user"
    ):
        """Place a new futures order."""
        try:
            if order_made_by not in ["bot", "user"]:
                raise ValueError("order_made_by must be 'bot' or 'user'")

            params = {}
            logger.info("Placing futures order for %s - \nSL: %s, TP: %s", symbol, stop_loss, take_profit)

            # Set leverage if provided
            if leverage:
                self.exchange.set_leverage(leverage, symbol)
                params["maxLeverage"] = leverage

            # Set risk parameters
            if take_profit:
                params["takeProfitPrice"] = float(take_profit)
            if stop_loss:
                params["stopLossPrice"] = float(stop_loss)

            # --- Lógica para cerrar posición opuesta ---
            try:
                open_positions = self.exchange.fetch_positions()
                for pos in open_positions:
                    pos_symbol = pos.get('symbol')
                    pos_side = pos.get('side')  # 'long' o 'short'
                    contracts = pos.get('contracts')
                    contracts_float = 0.0
                    if contracts is not None:
                        try:
                            contracts_float = float(contracts)
                        except (TypeError, ValueError):
                            contracts_float = 0.0
                    if pos_symbol == symbol and abs(contracts_float) > 0:
                        if (order_direction == "buy" and pos_side == "short") or (order_direction == "sell" and pos_side == "long"):
                            params["reduce_only"] = True
                            params["oflags"] = "fciq"
                            logger.info(f"[KrakenFutures] Se detectó posición opuesta abierta en {symbol}. Se usará reduce_only=True y oflags='fciq' para cerrar la posición.")
                            if volume > abs(contracts_float):
                                logger.info(f"[KrakenFutures] Ajustando volumen de cierre de {volume} a {abs(contracts_float)} para igualar la posición abierta.")
                                volume = abs(contracts_float)
                        break
            except Exception as e:
                logger.error(f"[KrakenFutures] Error al consultar posiciones abiertas: {e}")

            if order_direction not in ["buy", "sell"]:
                raise ValueError("Invalid order direction")
            else:
                # Execute order
                side = order_direction  # 'buy' or 'sell'
                print("amount = ",volume);
                order = self.exchange.create_order(
                    symbol=symbol,
                    type="market",
                    side=side,
                    amount=volume,
                    params=params
                )

            print(json.dumps(order, indent=4))

            # Prepare order record
            order_record = {
                "order_type": order_type,
                "order_direction": order_direction,
                "volume": float(volume),
                "symbol": symbol,
                "price": order.get("price"),
                "by": order_made_by,
                "order_id": order.get("id"),
                "user_id": self.user_id,
                "stop_loss": float(stop_loss) if stop_loss else 0,
                "take_profit": float(take_profit) if take_profit else 0,
                "exchange": "kraken-futures",
            }

            amount = float(volume) # BTC
            cost = float(order.get("cost")) # USDT
            price = float(order.get("price")) # USDT/BTC
            fees = abs(amount - (cost/price)) # BTC - (USDT/(USDT/BTC))
            # fees lo obtengo en cripto no en USDT

            print("amount:", amount)
            print("cost:", cost)
            print("price:", price)
            print("fees:", fees)

            if order_direction == "buy":
                order_record["volume"] = amount - fees

            # Save to database
            if not self.add_order_to_db(order_record):
                logger.error("Failed to save order to database")
                return None, "Database save error"

            # Reset leverage
            self.exchange.set_leverage(1, symbol)
            return order, fees, price, None

        except Exception as e:
            logger.error(f"Order placement error: {e}")
            traceback.print_exc()
            return None, None, None, str(e)

    def fetch_ohlcv_optimized(self, symbol, timeframe, limit=5):
        """Fetch optimized OHLCV data for LLM processing."""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            formatted = []
            
            for candle in ohlcv:
                dt = datetime.fromtimestamp(candle[0] / 1000)
                formatted.append({
                    "timestamp": dt.strftime('%Y-%m-%d %H:%M:%S'),
                    "open": round(candle[1], 4),
                    "high": round(candle[2], 4),
                    "low": round(candle[3], 4),
                    "close": round(candle[4], 4),
                    "volume": round(candle[5], 2)
                })
            return formatted
        except Exception as e:
            logger.error(f"OHLCV error for {symbol}/{timeframe}: {e}")
            return []

    def get_market_context_for_llm(self, symbol, timeframes_to_monitor):
        """Prepare market context data for LLM analysis."""
        market_context = {}
        for tf in timeframes_to_monitor:
            try:
                market_context[tf] = self.fetch_ohlcv_optimized(symbol, tf)
            except Exception as e:
                market_context[tf] = {"error": str(e)}
                logger.error(f"Market context error ({tf}): {e}")
        return market_context