import traceback
import ccxt
from app.viewmodels.api.kraken.KrakenAPI import KrakenAPI

API_KEY = "PbyEvuaUD9ShIIuaiB4FTsZDOLgiBeUNEZWnkgaZ8aIidEqN98ESsL2G9k7H5TVjtrbnVwOjbZLhBgKJrbg"
API_SECRET = "fFahVhTrozw7TQJVzf0EpP02zIpP1eBFgMnVFCMElp210RCDZsdTxHiqW2QZ29AA5e34BfCtM55DiIxsAnQ"
API_KEY_FUTURES = "PbyEvuaUD9ShIIuaiB4FTsZDOLgiBeUNEZWnkgaZ8aIidEqN98ESsL2G9k7H5TVjtrbnVwOjbZLhBgKJrbg"
API_SECRET_FUTURES = "fFahVhTrozw7TQJVzf0EpP02zIpP1eBFgMnVFCMElp210RCDZsdTxHiqW2QZ29AA5e34BfCtM55DiIxsAnQ"


class BingxExchange(KrakenAPI):
    def __init__(self, trading_mode="spot", user_id=None) -> None:
        """
        Initialize a BingxExchange instance.

        Args:
            trading_mode (str): The trading mode to use, defaults to "spot". Can be "spot" or "swap" for futures.
            user_id (Optional[str]): The user ID associated with this exchange instance, defaults to None.

        Attributes:
            exchange (ccxt.Exchange): The ccxt Bingx exchange object configured with API credentials and trading mode.
            user_id (Optional[str]): The user ID associated with this exchange instance.
        """

        self.exchange = ccxt.bingx(
            {
                "apiKey": API_KEY,
                "secret": API_SECRET,
                "options": {
                    "defaultType": trading_mode,
                },
                "enableRateLimit": True,  # Recommended to avoid hitting rate limits
            }
        )
        self.user_id = user_id
        self.trading_mode = trading_mode

    def get_symbol_price(self, symbol):
        try:
            price = self.exchange.fetch_ticker(symbol)["last"]
            return price, None
        except Exception as e:
            print(traceback.format_exc())
            return None, str(e)

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
            order = self.exchange.create_market_buy_order(
                symbol,
                volume,
                params=params
            )
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

        import json
        print(f":white_check_mark: Order saved to database: {json.dumps(order, indent=4)}")
        return order_saved, 200

    def get_tickers_available_symbols(self):
        markets = self.exchange.load_markets()
        print("Available markets:")
        for market in markets:
            print(market)

        return markets

    def get_account_balance(self):
        try:
            balance = self.exchange.fetch_balance()
            balance_list = []

            if self.trading_mode == "swap":
                for currency, amount in balance.get("total", {}).items():
                    balance_list.append({
                        "currency": currency.upper(),
                        "amount": float(amount)
                    })
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