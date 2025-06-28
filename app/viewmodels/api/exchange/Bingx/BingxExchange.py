"""BingxExchange module provides an interface to interact with the BingX exchange using ccxt."""

import json
import traceback
from datetime import datetime

import ccxt
from app.config import config

from app.viewmodels.api.exchange.FatherExchange import Exchange

# Este es el equivalente al BingxExchange que se tenia anteriormente
class BingxExchange(Exchange):
    """
    Class BingxExchange
    """

    def __init__(self, trading_mode = "spot", user_id = None) -> None:
        """
        Initialize a BingxExchange instance.

        Args:
            trading_mode (str): The trading mode to use, defaults to "spot". Can be "spot" or "swap" for futures.
            user_id (Optional[str]): The user ID associated with this exchange instance, defaults to None.

        Attributes:
            exchange (ccxt.Exchange): The ccxt Bingx exchange object configured with API credentials and trading mode.
            user_id (Optional[str]): The user ID associated with this exchange instance.
        """
        super().__init__(user_id, trading_mode)

        self.exchange = ccxt.bingx(
            {
                "apiKey": config.BINGX_API_KEY,
                "secret": config.BINGX_API_SECRET,
                "options": {
                    "defaultType": trading_mode,
                },
                "enableRateLimit": True,  # Recommended to avoid hitting rate limits
            }
        )
        
        self.user_id = user_id
        self.trading_mode = trading_mode

    def identification(self):
        return "Bingx"

    # Implementación específica de Bingx
    def get_creds_from_user(self):
        raise NotImplementedError("Método no disponible para este exchange")     

    def set_trading_mode(self, mode: str):
        raise NotImplementedError("Método no disponible para este exchange")

    def get_cryptos(self):
        try:
            tickers = self.exchange.fetch_tickers()
            symbols = [
                {"symbol": symbol, "price": data["last"]}
                for symbol, data in tickers.items()
            ]
            return symbols, None
        except Exception as e:
            print(traceback.format_exc())
            return [], str(e)

    def get_tickers_available_symbols(self):
        markets = self.exchange.load_markets()
        print("Available markets:")
        for market in markets:
            print(market)

        return markets

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
        volume = float(volume)
        print(
            f"🤑 [{self.trading_mode}] Placing market {order_direction} order for {volume} {symbol}..."
        )

        params = {}
        leverage = 10

        if stop_loss and stop_loss > 0:
            params["stopLossPrice"] = stop_loss

        if take_profit and take_profit > 0:
            params["takeProfitPrice"] = take_profit

        if leverage and leverage > 0:
            params["leverage"] = leverage

        if order_direction == "buy":
            params["positionSide"] = "LONG"
            order = self.exchange.create_market_buy_order(symbol, volume, params=params)
        else:
            params["positionSide"] = "SHORT"
            order = self.exchange.create_market_sell_order(
                symbol,
                volume,
                params=params,
            )

        # Save the order to the database
        order_to_save = {
            "order_type": order_type,
            "order_direction": order_direction,
            "volume": volume,
            "symbol": symbol,
            "price": order.get("price"),
            "by": order_made_by,
            "order_close_condition": order.get("stopLossPrice"),
            "order_description": None,
            "order_id": order.get("id"),
            "user_id": self.user_id,
            "stop_loss": order.get("stopLossPrice") or 0,
            "take_profit": order.get("takeProfitPrice") or 0,
            "leverage": leverage,
            "exchange": (
                "bingx-spot" if self.trading_mode == "spot" else "bingx-futures"
            ),
            "trading_mode": self.trading_mode,
        }

        order_saved = self.add_order_to_db(order_to_save)
        if not order_saved:
            return {"error": "Error saving order to database"}, 500

        print(
            f":white_check_mark: Order saved to database: {json.dumps(order, indent=4)}"
        )
        return order_saved, 200

    def get_symbol_price(self, symbol):
        # Validate symbol before making API call
        if not symbol or symbol.lower() == "null":
            return None, "Invalid symbol provided"
        try:
            price = self.exchange.fetch_ticker(symbol)["last"]
            return price, None
        except Exception as e:
            print(traceback.format_exc())
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

    def sign(self, data: dict) -> str:
        print("Firmando datos en Bingx")
        return "datos_firmados_bingx"
    
    def get_account_balance(self):
        try:
            balance = self.exchange.fetch_balance()
            balance_list = []

            if self.trading_mode == "swap":
                for currency, amount in balance.get("total", {}).items():
                    balance_list.append(
                        {"currency": currency.upper(), "amount": float(amount)}
                    )
                return balance_list

            for b in balance["info"]["data"]["balances"]:
                balance_list.append(
                    {
                        "currency": b["asset"],
                        "amount": float(b["free"]),  # Convert string to float
                    }
                )
            return balance_list
        except Exception as e:
            traceback.print_exc()
            return {"error": str(e)}