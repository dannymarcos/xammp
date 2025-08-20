import logging
import flask
from app.viewmodels.api.exchange.Exchange import ExchangeFactory
from app.viewmodels.wallet.found import Wallet

logger = logging.getLogger(__name__)

def process_order(user_id: int, data: dict, handle_user_balance: dict) -> tuple[bool, float]:
	wallet = Wallet(user_id)
	exchange_id = "kraken_futures"
	try:
		amount = float(data.get("amount"))
		leverage = float(data.get("leverage"))
		price = float(data.get("price"))
	except (TypeError, ValueError):
		logger.error("Invalid amount, leverage or price")
		return False, 0.00

	symbol = data.get("symbol")
	symbol_base = symbol.split("/")[0] if symbol and "/" in symbol else symbol
	
	params = {"user_id": user_id, "name": "kraken_future"}
	exchange = ExchangeFactory().create_exchange(**params)
	
	# Validación de saldos
	if data.get("orderDirection") == "buy":
		if not wallet.has_balance_in_currency(price, "USDT", "USDT", "general"):
			logger.error(f"Insufficient USDT balance: {price}")
			return False, 0.00
	elif data.get("orderDirection") == "sell":
		required_balance = amount * leverage
		# if handle_user_balance[user_id]['cripto'] < required_balance:
		# 	logger.error(f'Insufficient {symbol_base} balance: {required_balance}')
		# 	return False, 0.00
		# if not wallet.has_balance_in_currency(required_balance, symbol_base, symbol_base, exchange_id):
		#     logger.error(f"Insufficient {symbol_base} balance: {required_balance}")
		#     return False, 0.00
	else:
		logger.error("Invalid order direction")
		return False, 0.00

	if not flask.has_app_context():
		from app.__init__ import create_app
		app = create_app()
		with app.app_context():
			order_result = exchange.add_order(
				leverage=data.get("leverage"),
				order_type=data.get("orderType"),
				volume=data.get("amount"),
				symbol=data.get("symbol"),
				order_made_by=data.get("order_made_by"),
				order_direction=data.get("orderDirection")
			)
	else:
		order_result = exchange.add_order(
			leverage=data.get("leverage"),
			order_type=data.get("orderType"),
			volume=data.get("amount"),
			symbol=data.get("symbol"),
			order_made_by=data.get("order_made_by"),
			order_direction=data.get("orderDirection")
		)

	if isinstance(order_result, tuple):
		order, fees, price_cripto_in_usdt, error = order_result
		status_code = 200 if error is None else 400
	else:
		order = order_result
		error = None
		status_code = 200

	if error is not None or status_code != 200:
		return False, 0.00

	try:
		total_usdt = amount * float(price_cripto_in_usdt)
		fees = float(fees)
		if data.get("orderDirection") == "buy":
			margin_used = amount * leverage
			amount_obtained = margin_used - fees

			wallet.add_blocked_balance(
				amount_usdt=-total_usdt,
				amount_crypto=amount_obtained,
				currency="BTC/USDT",
				by_bot=data["order_made_by"]
			)
			# handle_user_balance[user_id]["usd"] += -total_usdt
			# handle_user_balance[user_id]["cripto"] += amount_obtained
		elif data.get("orderDirection") == "sell":
			fees_in_usdt = fees * float(price_cripto_in_usdt)
			net_usdt_received = total_usdt - fees_in_usdt
			amount_obtained = -amount

			wallet.add_blocked_balance(
				amount_usdt=net_usdt_received,
				amount_crypto=-amount,
				currency="BTC/USDT",
				by_bot=data["order_made_by"]
			)

			# handle_user_balance[user_id]["usd"] += net_usdt_received
			# handle_user_balance[user_id]["cripto"] += -amount
		else:
			return False, 0.00
	except Exception as wallet_error:
		logger.error(f"Wallet transaction error: {wallet_error}")
		return False, 0.00

	return True, amount_obtained
