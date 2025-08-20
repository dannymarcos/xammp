import logging
import flask
from app.viewmodels.api.exchange.Exchange import ExchangeFactory
from app.iu.routes.tradings.trading_routes import validate_master_account_balance
from app.viewmodels.wallet.found import Wallet

logger = logging.getLogger(__name__)

def process_order(user_id: int, data: dict) -> tuple[bool, float]:
    wallet = Wallet(user_id)
    exchange_id = "kraken_spot"

    ordertype = data.get("orderType")
    order_direction = data.get("orderDirection")
    volume = float(data.get("amount"))
    symbol = data.get("symbol", "BTC/USD")
    price = data.get("price", 0)
    order_made_by = data.get("order_made_by", "user")

    if order_direction == "buy":
        required_params = [ordertype, symbol, order_made_by, volume]
        if not all(required_params):
            return False, 0.00
    elif order_direction == "sell":
        required_params = [ordertype, order_direction, volume, symbol, order_made_by]
        if not all(required_params):
            return False, 0.00

    exchange = ExchangeFactory().create_exchange(name="kraken_spot", user_id=user_id)

    # Get current price if not provided
    if price == 0:
        price_data = exchange.get_symbol_price(symbol)
        if isinstance(price_data, tuple):
            price = price_data[0]
        else:
            price = price_data

    if order_direction == "buy":
        if not wallet.has_balance_in_currency(volume, 'USDT', 'USDT', 'general'):
            logger.error(f'Insufficient USDT balance: {volume}')
            return False, 0.00
        
        is_valid, _ = validate_master_account_balance(volume, 'USD.F', exchange_id)
        if not is_valid:
            logger.error('Master account USDT balance insufficient')
            return False, 0.00
    else:  # sell
        symbol_base = symbol.split("/")[0]
        if wallet.get_blocked_balance(currency="BTC/USDT", by_bot=data["order_made_by"])["amount_crypto"] < volume:
            logger.error(f'Insufficient {symbol_base} balance: {volume}')
            return False, 0.00

        is_valid, _ = validate_master_account_balance(volume, symbol_base + ".F", exchange_id)
        if not is_valid:
            return False, 0.00

    if not flask.has_app_context():
        from app.__init__ import create_app
        app = create_app()
        with app.app_context():
            response = exchange.add_order(
                order_type=ordertype,
                order_direction=order_direction,
                volume=volume,
                symbol=symbol,
                price=price,
                order_made_by=order_made_by
            )
    else:
        response = exchange.add_order(
            order_type=ordertype,
            order_direction=order_direction,
            volume=volume,
            symbol=symbol,
            price=price,
            order_made_by=order_made_by
        )

    if response[0] is None and "Insufficient funds" in response[1]:
        return False, 0.00

    order_id = response[0]["id"]
    data_for_order = exchange.get_kraken_order_details(order_id)
    filled = data_for_order["filled"]
    cost = data_for_order["cost"]
    fee = data_for_order["fee"]

    if isinstance(response, tuple):
        order, error = response
        if error:
            return False, 0.00
    else:
        order = response
        error = None

    if error is None:
        try:
            symbol_base = symbol.split("/")[0]
            symbol_base_1 = symbol.split("/")[1]
            # amount_obtained_from_the_order_crypto = filled - fee[symbol_base]

            if order_direction == "buy":
                wallet.add_blocked_balance(
                    amount_usdt=-(cost - fee[symbol_base_1]),
                    amount_crypto=filled,
                    currency="BTC/USDT",
                    by_bot=data["order_made_by"]
                )
                # handle_user_balance[user_id]["usd"] += -(cost - fee[symbol_base_1])
                # handle_user_balance[user_id]["cripto"] += filled
            elif order_direction == "sell":
                wallet.add_blocked_balance(
                    amount_usdt=(cost - fee[symbol_base_1]),
                    amount_crypto=filled,
                    currency="BTC/USDT",
                    by_bot=data["order_made_by"]
                )
                # handle_user_balance[user_id]["usd"] += (cost - fee[symbol_base_1])
                # handle_user_balance[user_id]["cripto"] += filled
        except Exception as wallet_error:
            return False, 0.00

    return True, 0.00
