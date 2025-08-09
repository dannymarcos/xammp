import json
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
import logging, traceback, os, time
from app.viewmodels.api.spot.KrakenSpotApiGetAccountBalance import KrakenSpotApiGetAccountBalance
from app.viewmodels.services.GetMethodTrading import GetMethodTrading
from app.viewmodels.services.GetSymbolTrading import GetSymbolTrading
from app.viewmodels.api.spot.KrakenSpotAPITicker import KrakenSpotAPI
from app.viewmodels.api.exchange.Exchange import ExchangeFactory
from app.models.trades import get_all_trades_from_user
from app.viewmodels.wallet.found import Wallet, WalletAdmin
from app.config import config
import requests

trading_bp = Blueprint('trading', __name__)
logger = logging.getLogger(__name__)
method_instance = GetMethodTrading()
symbol_instance = GetSymbolTrading()

def validate_master_account_balance(required_amount: float, currency: str, exchange_id: str) -> tuple[bool, str]:
    try:
        wallet_admin = WalletAdmin()
        real_balances = wallet_admin.get_real_master_account_balances()
        
        # Get the balance data for the specific exchange
        exchange_balance_data = real_balances.get(exchange_id, {})
        
        if exchange_balance_data.get("error"):
            return False, f"Error getting master account balance for {exchange_id}: {exchange_balance_data['error']}"
        
        balances = exchange_balance_data.get("balances", [])
        
        # Find the required currency in the balances
        currency_balance = 0
        for balance in balances:
            if balance.get("currency", "").upper() == currency.upper():
                currency_balance = float(balance.get("amount", 0))
                break
        
        if currency_balance < required_amount:
            return False, f"Insufficient master account balance. Required: {required_amount} {currency}, Available: {currency_balance} {currency}"
        
        return True, ""
        
    except Exception as e:
        logger.error(f"Error validating master account balance: {e}")
        return False, f"Error validating master account balance: {str(e)}"

def get_commission_rate(trading_mode: str, order_direction: str) -> float:
    if trading_mode == "spot":
        if order_direction == "buy":
            return config.KRAKEN_SPOT_COMISION_BUY
        else:
            return config.KRAKEN_SPOT_COMISION_SELL
    elif trading_mode == "futures":
        if order_direction == "buy":
            return config.KRAKEN_FUTURES_COMISION_BUY
        else:
            return config.KRAKEN_FUTURES_COMISION_SELL
    elif trading_mode == "bingx-spot":
        if order_direction == "buy":
            return config.BINGX_SPOT_COMISION_BUY
        else:
            return config.BINGX_SPOT_COMISION_SELL
    elif trading_mode == "bingx-futures":
        if order_direction == "buy":
            return config.BINGX_FUTURES_COMISION_BUY
        else:
            return config.BINGX_FUTURES_COMISION_SELL
    else:
        # Default
        return 0.001

def calculate_amount_with_commission(base_amount: float, trading_mode: str, order_direction: str) -> float:
    value_in_usdt = base_amount

    commission_rate = get_commission_rate(trading_mode, order_direction)
    return base_amount - (value_in_usdt * commission_rate)

@trading_bp.route("/get_account_balance", methods =["POST"])
@login_required
def get_account_balance():
    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        data = request.get_json()
        trading_mode = data.get("trading_mode")
        exchange_name = data.get("exchange_name")
        API_KEY_KRAKEN = os.getenv("KRAKEN_API_KEY")
        API_SECRET_KRAKEN = os.getenv("KRAKEN_API_SECRET")
        exchange_config = {
            "spot": {"handler": KrakenSpotApiGetAccountBalance(), "special_case": True},
            "futures": {"factory_name": "kraken_future", "error_status": 500},
            "bingx-spot": {"factory_name": "bingx", "error_status": 400},
            "bingx-futures": {"factory_name": "bingx", "trading_mode": "swap", "error_status": 400}
        }
        
        # Map trading modes to exchange identifiers for balance filtering
        exchange_mapping = {
            "spot": "kraken_spot",
            "futures": "kraken_futures", 
            "bingx-spot": "bingx_spot",
            "bingx-futures": "bingx_futures"
        }
        
        # Get the exchange identifier for balance filtering
        exchange_id = exchange_mapping.get(trading_mode, "general")
        
        wallet = Wallet(current_user.id)
        balance = wallet.get_balance(exchange=exchange_id)
        for item in balance:
            if 'id' in item:
                del item['id']
            if 'user_id' in item:
                del item['user_id']

        return jsonify({"balance": balance})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@trading_bp.route("/get_method_trading")
@login_required
def get_method_trading():
    try:
        trading_mode = method_instance.get_method()
        return jsonify({"method": trading_mode})
    except Exception as e:
        logger.error(f"Error getting cryptocurrencies: {e}")
        return jsonify({"error": str(e)}), 500

@trading_bp.route("/get_symbol_trading")
@login_required
def get_symbol_trading():
    try:
        symbol = symbol_instance.get_symbol()
        return jsonify({"symbol": symbol})
    except Exception as e:
        logger.error(f"Error getting cryptocurrencies: {e}")
        return jsonify({"error": str(e)}), 500

@trading_bp.route("/get_cryptos", methods=['POST'])
@login_required
def get_cryptos():
    try:
        data = request.get_json()
        exchange_name = data.get("exchange_name")
        factory_map = {
            "futures":      {"name": "kraken_future", "trading_mode": None},
            "spot":         {"name": "kraken_spot",   "trading_mode": None},
            "bingx-spot":   {"name": "bingx",         "trading_mode": "spot"},
            "bingx-futures":{"name": "bingx",         "trading_mode": "swap"},
        }
        if exchange_name not in factory_map:
            return jsonify({"error": "Invalid exchange name"}), 400
        factory_args = {"name": factory_map[exchange_name]["name"], "user_id": current_user.id}
        if factory_map[exchange_name]["trading_mode"]:
            factory_args["trading_mode"] = factory_map[exchange_name]["trading_mode"]
        exchange = None
        if exchange_name != "spot":
            exchange = ExchangeFactory().create_exchange(**factory_args)
        if exchange_name == "futures":
            if hasattr(exchange, "get_cryptos"):
                cryptos, status = exchange.get_cryptos()
                if status != 200:
                    logger.error(f"Futures symbols error: {cryptos}")
                    return jsonify({"cryptos": cryptos}), status
                return jsonify({"cryptos": cryptos})
            else:
                return jsonify({"error": "Not supported"}), 500
        elif exchange_name == "spot":
            spot_client = KrakenSpotAPI()
            cryptos = spot_client.get_symbol_and_ultimate_price_trade()
            return jsonify(cryptos)
        elif exchange_name in ["bingx-spot", "bingx-futures"]:
            cryptos, err = exchange.get_cryptos()
            if err:
                logger.error(f"Bingx ticker error: {cryptos}")
                return jsonify({"error": f"Bingx ticker error: {cryptos}"}), 400
            return jsonify({"cryptos": cryptos})
        return jsonify({"error": "Invalid trading mode"}), 400
    except Exception as e:
        logger.error(f"Error getting cryptocurrencies: {e}")
        return jsonify({"error": str(e)}), 500


@trading_bp.route("/get_symbol_price", methods=['GET'])
@login_required
#for single crypto with symbol
def get_symbol_price():
    """Get available cryptocurrencies"""
    try:
        symbol = request.args.get('symbol')
        if not symbol:
            return jsonify({"error": "Symbol not provided"}), 400
        
        exchange = request.args.get('exchange')
        if exchange == "kraken-futures":
            kraken = ExchangeFactory().create_exchange(name="kraken_future", user_id=current_user.id)
            data = kraken.get_symbol_price(symbol)

            return {"price": data[0], "symbol": symbol}
        elif exchange == "kraken-spot":
            kraken = ExchangeFactory().create_exchange(name="kraken_spot", user_id=current_user.id)
            data = kraken.get_symbol_price(symbol)
            
            return {"price": data[0]["price"], "symbol": symbol}
        elif exchange == "bingx-spot" or exchange == "bingx-futures":
            bingx_client = ExchangeFactory().create_exchange(name="bingx", user_id=current_user.id)
            price, error = bingx_client.get_symbol_price(symbol)
            if error:
                logger.error(f"Bingx ticker error: {price}")
                return jsonify({"error": f"Bingx ticker error: {price}"}), 400
            
            return jsonify({"price": price , "symbol": symbol})

        spot_client = ExchangeFactory().create_exchange(name="kraken_spot", user_id=current_user.id)
        data = spot_client.get_symbol_price(symbol)
        if data[1] != 200:
            return jsonify(data[0]), data[1]
        
        return jsonify(data[0])

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@trading_bp.route("/trades", methods=['GET'])
@login_required
def get_user_trades():
    try:
        by = request.args.get("by")
        if not current_user.is_authenticated:
            return jsonify({"error": "User not authenticated"}), 401
        trades = get_all_trades_from_user(current_user.id, by)
        return jsonify({"trades": trades})
    except Exception as e:
        logger.error(f"Error getting cryptocurrencies: {e}")
        return jsonify({"error": str(e)}), 500

@trading_bp.route("/close_order", methods=["POST"])
@login_required
def close_order():
    try:
        data = request.get_json()
        trading_mode = data.get("trading_mode")
        user_id = current_user.id
        exchange = ExchangeFactory().create_exchange(name="kraken_future", user_id=user_id)
        if trading_mode == "spot":
            return jsonify({"error": "Spot trading mode not supported"}), 400
        elif trading_mode == "futures":
            exchange.close_order(symbol=data.get("symbol"), side=data.get("orderDirection"), params=data.get("params"))
        else:
            return jsonify({"error": "Invalid trading mode"}), 400
        return jsonify({"message": "Order closed successfully"}), 200   
    except Exception as e:
        logger.error(f"Error closing order: {e}")
        return jsonify({"error": str(e)}), 500


def get_current_price(exchange, symbol):
    asset_price = None

    try:
        current_price = exchange.get_symbol_price(symbol)

        if isinstance(current_price, tuple):
            asset_price = current_price[0]
        elif isinstance(current_price, dict) and "price" in current_price:
            asset_price = current_price["price"]
        else:
            asset_price = current_price            
    except Exception as price_error:
        logger.error(f"Error getting current price for {symbol}: {price_error}")

    return asset_price


# verify
@trading_bp.route("/add_order", methods=["POST"])
@login_required
def add_order():
    try:
        data = request.get_json()
        trading_mode = data.get("trading_mode")
        user_id = current_user.id
        wallet = Wallet(user_id)

        # Initialize WalletAdmin for recording transactions
        wallet_admin = WalletAdmin()

        # Map trading modes to exchange identifiers for balance filtering
        exchange_mapping = {
            "kraken-spot": "kraken_spot",
            "futures": "kraken_futures", 
            "bingx-spot": "bingx_spot",
            "bingx-futures": "bingx_futures"
        }
        
        # Get the exchange identifier for balance filtering
        exchange_id = exchange_mapping.get(trading_mode, "general")
                
        if trading_mode == "kraken-spot":
            ordertype = data.get("orderType")
            order_direction = data.get("orderDirection")
            volume = float(data.get("amount"))
            symbol = data.get("symbol", "BTC/USD")
            price = data.get("price", 0)
            order_made_by = data.get("order_made_by", "user")

            if order_direction == "buy":
                required_params = [ordertype, symbol, order_made_by, volume]
                if not all(required_params):
                    return jsonify({"error": f"Faltan parámetros requeridos {required_params}"}), 400
            elif order_direction == "sell":
                required_params = [ordertype, order_direction, volume, symbol, order_made_by]
                if not all(required_params):
                    return jsonify({"error": f"Faltan parámetros requeridos {required_params}"}), 400
            
            exchange = ExchangeFactory().create_exchange(name="kraken_spot", user_id=user_id)
            
            # Get current price if not provided
            if price == 0:
                print("=== symbol ===")
                print(symbol)
                print("=== symbol ===")
                price_data = exchange.get_symbol_price(symbol)
                if isinstance(price_data, tuple):
                    price = price_data[0]
                else:
                    price = price_data
            
            # Validate user balance
            # if order_direction == "buy":
            #     if not wallet.has_balance_in_currency(volume, "USDT", "USDT", "general"):
            #         return jsonify({"error": f"Insufficient USDT balance. Required: {volume} USDT"}), 400
                
                # Validate master account balance
                # is_valid, error_msg = validate_master_account_balance(volume, "USD", exchange_id)
                # if not is_valid:
                #     return jsonify({"error": error_msg}), 400
            # else:  # sell
            #     symbol_base = symbol.split("/")[0]
            #     if not wallet.has_balance_in_currency(volume, symbol_base, symbol_base, exchange_id):
            #         return jsonify({"error": f"Insufficient {symbol_base} balance. Required: {volume} {symbol_base}"}), 400
                
                # Validate master account balance
                # is_valid, error_msg = validate_master_account_balance(volume, symbol_base, exchange_id)
                # if not is_valid:
                #     return jsonify({"error": error_msg}), 400
            
            response = exchange.add_order(
                order_type=ordertype,
                order_direction=order_direction,
                volume=volume,
                symbol=symbol,
                price=price,
                order_made_by=order_made_by,
            )

            if(response[0] is None and "Insufficient funds" in response[1]):
                return jsonify({"error": "The master account does not have sufficient funds"}), 400
                
            order_id = response[0]["id"]

            print("===response===")
            print(order_id)
            print("===response===")

            data_for_order =  exchange.get_kraken_order_details(order_id)

            print(data_for_order)

            filled = data_for_order["filled"]
            cost = data_for_order["cost"]
            fee = data_for_order["fee"]
            
            # Handle response
            if isinstance(response, tuple):
                order, error = response
                if error:
                    return jsonify({"error": error, "success": False}), 400
            else:
                order = response
                error = None
            
            # Record transaction in wallet if order was successful
            if error is None:
                try:
                    symbol_base = symbol.split("/")[0]
                    symbol_base_1 = symbol.split("/")[1]
                    print("*"*30)
                    print(symbol_base)
                    print(symbol)
                    print(order_direction)
                    print("*"*30)
                    
                    if order_direction == "buy":
                        wallet_admin.add_found(user_id, filled - fee[symbol_base], symbol_base, exchange_id)
                        wallet_admin.add_found(user_id, -cost, "USDT", "general")
                    elif order_direction == "sell":
                        wallet_admin.add_found(user_id, -filled, symbol_base, exchange_id)
                        wallet_admin.add_found(user_id, cost - fee[symbol_base_1], "USDT", "general")
                except Exception as wallet_error:
                    logger.error(f"Error recording wallet transaction: {wallet_error}")
            
            return jsonify({"order": order, "success": True}), 200
        elif trading_mode in ["bingx-spot", "bingx-futures"]:
            symbol_base = data["symbol"].split("/")[0]
            params = {"user_id": current_user.id}

            if trading_mode == "bingx-spot":
                params["name"] = "bingx"
            elif trading_mode == "bingx-futures":
                params["name"] = "bingx"
                params["trading_mode"] = "swap"
            exchange = ExchangeFactory().create_exchange(**params)

            # Get current price and calculate total price
            current_price = get_current_price(exchange, data["symbol"])
            if current_price is None:
                return jsonify({"error": "Unable to get current price"}), 400
            
            amount = float(data["amount"])
            price = float(current_price) * amount
            leverage = float(data["leverage"])

            # Validate master account balance first
            if data["orderDirection"] == "buy":
                # Then check user's local balance
                if not wallet.has_balance_in_currency(price * leverage, "USDT", "USDT", "general"):
                    return jsonify({"error": f"Insufficient USDT balance, now price is {price} and amount is {leverage} and total is {price * leverage}"}), 400

                # For buy orders, check if master account has enough USDT
                is_valid, error_msg = validate_master_account_balance(price, "USDT", exchange_id)
                if not is_valid:
                    return jsonify({"error": error_msg}), 400
                
            elif data["orderDirection"] == "sell":
                # Then check user's local balance
                if not wallet.has_balance_in_currency(amount * leverage, symbol_base, symbol_base, exchange_id):
                    return jsonify({"error": f"Insufficient {symbol_base} balance. Required margin: {amount * leverage} {symbol_base}"}), 400

                if trading_mode == "bingx-spot":
                    # For sell orders, check if master account has enough of the base currency
                    is_valid, error_msg = validate_master_account_balance(amount * leverage, symbol_base, exchange_id)
                    if not is_valid:
                        return jsonify({"error": error_msg}), 400
            
            print("#"*30)
            print(data["symbol"])
            print("#"*30)

            order, fees, price_cripto_in_usdt, cost_in_usdt, fees_currency, status_code = exchange.add_order(
                leverage=data["leverage"],
                order_type=data["orderType"],
                volume=data["amount"],
                symbol=data["symbol"],
                order_made_by=data["order_made_by"],
                stop_loss=data["stopLoss"],
                take_profit=data["takeProfit"],
                order_direction=data["orderDirection"],
            )
            
            if status_code != 200:
                return jsonify({"error": order["error"], "success": False}), status_code
            
            price = amount * price_cripto_in_usdt

            # Record transaction in wallet if order was successful
            try:
                # Extract currency from symbol (e.g., "BTCUSDT" -> "USDT")
                symbol = data["symbol"]
                currency = symbol.split("/")[0]
                
                amount_traded = float(data["amount"]) * float(data["leverage"])

                if data["orderDirection"] == "buy":
                    print("fees:", fees)
                    print("fees_currency:", fees_currency)
                    print("price_cripto_in_usdt:", price_cripto_in_usdt)
                    print("amount_traded:", amount_traded)
                    print("comision:", (fees/price_cripto_in_usdt))

                    wallet_admin.add_found(user_id, amount_traded - (fees/price_cripto_in_usdt), currency, exchange_id)
                    wallet_admin.add_found(user_id, -cost_in_usdt, "USDT", "general")
                elif data["orderDirection"] == "sell":
                    wallet_admin.add_found(user_id, -amount_traded, currency, exchange_id)
                    wallet_admin.add_found(user_id, cost_in_usdt - fees, "USDT", "general")
            except Exception as wallet_error:
                logger.error(f"Error recording wallet transaction: {wallet_error}")
            
            return jsonify({"order": order, "success": True})
        elif trading_mode == "kraken-futures":
            # Validate balance for futures trading
            amount = float(data["amount"])
            leverage = float(data["leverage"])
            symbol_base = data["symbol"].split("/")[0]
            exchange_id = "kraken_futures"
            params = {"user_id": current_user.id, "name": "kraken_future"}
            exchange = ExchangeFactory().create_exchange(**params)

            current_price = get_current_price(exchange, data["symbol"])
            if current_price is None:
                return jsonify({"error": "Unable to get current price"}), 400
            
            price = float(current_price) * amount * leverage

            # Validate master account balance first
            if data["orderDirection"] == "buy":
                # Then check user's local balance
                if not wallet.has_balance_in_currency(price, "USDT", "USDT", "general"):
                    return jsonify({"error": f"Insufficient USDT balance for futures trading"}), 400

                # For buy orders, check if master account has enough USDT
                is_valid, error_msg = validate_master_account_balance(price, "USD", exchange_id)
                if not is_valid:
                    return jsonify({"error": error_msg}), 400
                
            elif data["orderDirection"] == "sell":
                # Then check user's local balance
                if not wallet.has_balance_in_currency(amount * leverage, symbol_base, symbol_base, exchange_id):
                    return jsonify({"error": f"Insufficient {symbol_base} balance for futures trading. Required margin: {amount * leverage} {symbol_base}"}), 400

            order_result, fees, price_cripto_in_usdt, error = exchange.add_order(
                leverage=data["leverage"],
                order_type=data["orderType"],
                volume=data["amount"],
                symbol=data["symbol"],
                order_made_by=data["order_made_by"],
                stop_loss=data["stopLoss"],
                take_profit=data["takeProfit"],
                order_direction=data["orderDirection"],
            )
            
            # Handle tuple response (order_data, status_code)
            if isinstance(order_result, tuple):
                order, status_code = order_result
            else:
                order = order_result
                status_code = 200
                
            
            # Record transaction in wallet if order was successful
            if error is None:
                try:
                    total_usdt = amount * price_cripto_in_usdt

                    if data["orderDirection"] == "buy":
                        margin_used = amount * leverage

                        wallet_admin.add_found(user_id, margin_used - fees, symbol_base, exchange_id)
                        wallet_admin.add_found(user_id, -total_usdt, "USDT", "general")
                    elif data["orderDirection"] == "sell":
                        fees_in_usdt = fees * price_cripto_in_usdt
                        net_usdt_received = total_usdt - fees_in_usdt

                        wallet_admin.add_found(user_id, net_usdt_received, "USDT", "general")
                        wallet_admin.add_found(user_id, -amount, symbol_base, exchange_id)
                except Exception as wallet_error:
                    logger.error(f"Error recording wallet transaction: {wallet_error}")
            
            if error is not None:
                return jsonify({"error": error, "success": False}), 400
            return jsonify({"order": order, "success": True}), status_code
        else:
            return jsonify({"error": f"Modo de trading inválido {trading_mode}"}), 400
    except Exception as e:
        logger.error("Error en add_order: %s", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@trading_bp.route("/get_current_symbol", methods=["GET"])
def get_current_symbol():
    try:
        if os.path.exists("current_symbol.txt"):
            with open("current_symbol.txt", "r") as f:
                symbol = f.read().strip()
        else:
            symbol = "BTCUSD"
        return jsonify({"symbol": symbol})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@trading_bp.route("/update_current_symbol", methods=["POST"])
def update_current_symbol():
    try:
        data = request.get_json()
        new_symbol = data.get("symbol")
        with open("current_symbol.txt", "w") as f:
            f.write(new_symbol)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Error updating current symbol: {e}")
        return jsonify({"error": str(e)}), 500

@trading_bp.route("/fetch_historical_data")
def fetch_historical_data():
    symbol = request.args.get("symbol", "XBTUSD")  # Símbolo por defecto: XBTUSD
    interval = 15  # Intervalo de 15 minutos
    since = int(time.time() - (30 * 24 * 60 * 60))  # Últimos 30 días

    try:
        url = "https://api.kraken.com/0/public/OHLC"
        params = {
            "pair": symbol,
            "interval": interval,
            "since": since
        }

        response = requests.get(url, params=params)
        if response.status_code != 200:
            return jsonify({"error": f"HTTP error {response.status_code}: {response.text}"}), 400

        data = response.json()
        if "error" in data and data["error"]:
            return jsonify({"error": f"Kraken API error: {data['error']}"}), 400

        result = data.get("result", {})
        if not result:
            return jsonify({"error": "No historical data found"}), 400

        pair_data = next(iter(result.values()))
        return jsonify(pair_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500