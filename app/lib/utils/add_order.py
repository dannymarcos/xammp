"""
	add_order lo usa ambos bots para poder comprar/vender con los exchange
	
	TODO: Hacer que trading_routes.py tambien dependa de este add_order para
	tener una sola funcion que haga esto
"""

import logging
from app.iu.routes.tradings.trading_routes import get_current_price, validate_master_account_balance
from app.viewmodels.api.exchange.Exchange import ExchangeFactory
from app.viewmodels.wallet.found import Wallet, WalletAdmin

logger = logging.getLogger(__name__)

def add_order(user_id: int, data: dict, trading_mode: str) -> bool:
	try:
		print(f"[add_order] user_id={user_id}")
		print(f"[add_order] trading_mode={trading_mode}")
		print(f"[add_order] data={data}")
		wallet = Wallet(user_id)
		wallet_admin = WalletAdmin()

		exchange_id = trading_mode
		if trading_mode == "kraken_spot":
			ordertype = data.get("orderType")
			order_direction = data.get("orderDirection")
			volume = float(data.get("amount"))
			symbol = data.get("symbol", "BTC/USD")
			price = data.get("price", 0)
			order_made_by = data.get("order_made_by", "user")

			if order_direction == "buy":
				required_params = [ordertype, symbol, order_made_by, volume]
				if not all(required_params):
					return False
			elif order_direction == "sell":
				required_params = [ordertype, order_direction, volume, symbol, order_made_by]
				if not all(required_params):
					return False
			
			exchange = ExchangeFactory().create_exchange(name="kraken_spot", user_id=user_id)
			
			# Get current price if not provided
			if price == 0:
				price_data = exchange.get_symbol_price(symbol)
				if isinstance(price_data, tuple):
					price = price_data[0]
				else:
					price = price_data
			
			response = exchange.add_order(
				order_type=ordertype,
				order_direction=order_direction,
				volume=volume,
				symbol=symbol,
				price=price,
				order_made_by=order_made_by,
			)

			if(response[0] is None and "Insufficient funds" in response[1]):
				return False
				
			order_id = response[0]["id"]

			data_for_order =  exchange.get_kraken_order_details(order_id)

			filled = data_for_order["filled"]
			cost = data_for_order["cost"]
			fee = data_for_order["fee"]
			
			# Handle response
			if isinstance(response, tuple):
				order, error = response
				if error:
					return False
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
					return False
			
			return True
		elif trading_mode in ["bingx_spot", "bingx_futures"]:
			symbol_base = data["symbol"].split("/")[0]
			if trading_mode == "bingx_spot":
				data["symbol"] = data["symbol"].replace(":USDT", "")
			elif trading_mode == "bingx_futures":
				if ":USDT" not in data["symbol"]:
					data["symbol"] = data["symbol"] + ":USDT"
			params = {"user_id": user_id}

			print(f"[add_order] params before assignment: {params}")
			if trading_mode == "bingx_spot":
				params["name"] = "bingx"
				params["trading_mode"] = "spot"
			elif trading_mode == "bingx_futures":
				params["name"] = "bingx"
				params["trading_mode"] = "swap"
			print(f"[add_order] params after assignment: {params}")

			exchange = ExchangeFactory().create_exchange(**params)
			print(f"[add_order] exchange created: {exchange}")
			current_price = get_current_price(exchange, data["symbol"])
			print(f"[add_order] current_price: {current_price}")

			if current_price is None:
				logger.error("Failed to get current price")
				return False

			amount = float(data["amount"])
			leverage = float(data["leverage"])
			price = float(current_price) * amount
			total_cost = price * leverage

			print(f"[add_order] amount={amount}, leverage={leverage}, price={price}, total_cost={total_cost}")

			# Validación de saldos
			if data["orderDirection"] == "buy":
				if not wallet.has_balance_in_currency(total_cost, "USDT", "USDT", "general"):
					logger.error(f"Insufficient USDT balance: {total_cost}")
					return False

				is_valid, _ = validate_master_account_balance(price, "USDT", exchange_id)
				if not is_valid:
					logger.error("Master account USDT balance insufficient")
					return False
			elif data["orderDirection"] == "sell":
				required_balance = amount * leverage
				if not wallet.has_balance_in_currency(required_balance, symbol_base, symbol_base, exchange_id):
					logger.error(f"Insufficient {symbol_base} balance: {required_balance}")
					return False

				if trading_mode == "bingx_spot":
					is_valid, _ = validate_master_account_balance(required_balance, symbol_base, exchange_id)
					if not is_valid:
						logger.error(f"Master account {symbol_base} balance insufficient")
						return False

			print(f"[add_order] order params: leverage={data['leverage']}, order_type={data['orderType']}, volume={data['amount']}, symbol={data['symbol']}, order_direction={data['orderDirection']}")
			order_result = exchange.add_order(
				leverage=data["leverage"],
				order_type=data["orderType"],
				volume=data["amount"],
				symbol=data["symbol"],
				stop_loss=None,
				take_profit=None,
				order_direction=data["orderDirection"],
			)

			print(f"[add_order] order_result: {order_result}")

			if isinstance(order_result, tuple):
				order, fees, price_cripto_in_usdt, cost_in_usdt, fees_currency, status_code = order_result
			else:
				return False

			if status_code != 200:
				return False

			try:
				currency = data["symbol"].split("/")[0]
				amount_traded = float(data["amount"]) * leverage
				cost_in_usdt = float(cost_in_usdt)
				fees = float(fees)

				print(f"[add_order] wallet movements: currency={currency}, amount_traded={amount_traded}, cost_in_usdt={cost_in_usdt}, fees={fees}")

				if data["orderDirection"] == "buy":
					wallet_admin.add_found(
						user_id,
						amount_traded - (fees / price_cripto_in_usdt),
						currency,
						exchange_id
					)
					wallet_admin.add_found(
						user_id,
						-cost_in_usdt,
						"USDT",
						"general"
					)
				elif data["orderDirection"] == "sell":
					wallet_admin.add_found(
						user_id,
						-amount_traded,
						currency,
						exchange_id
					)
					wallet_admin.add_found(
						user_id,
						cost_in_usdt - fees,
						"USDT",
						"general"
					)
			except Exception as wallet_error:
				logger.error(f"Wallet transaction error: {wallet_error}")
				return False

			return True
		elif trading_mode == "kraken_futures":
			amount = float(data["amount"])
			leverage = float(data["leverage"])
			price = float(data.get("price"))
			symbol_base = data["symbol"].split("/")[0]
			exchange_id = "kraken_futures"
			params = {"user_id": user_id, "name": "kraken_future"}
			exchange = ExchangeFactory().create_exchange(**params)

			# Validación de saldos
			if data["orderDirection"] == "buy":
				if not wallet.has_balance_in_currency(price, "USDT", "USDT", "general"):
					logger.error(f"Insufficient USDT balance: {price}")
					return False

				# is_valid, _ = validate_master_account_balance(price, "USDT", exchange_id)
				# if not is_valid:
				#     logger.error("Master account USD balance insufficient")
				#     return False
				
			elif data["orderDirection"] == "sell":
				required_balance = amount * leverage
				if not wallet.has_balance_in_currency(required_balance, symbol_base, symbol_base, exchange_id):
					logger.error(f"Insufficient {symbol_base} balance: {required_balance}")
					return False
			
			if "kraken" in trading_mode:
				order_result = exchange.add_order(
					leverage=data["leverage"],
					order_type=data["orderType"],
					volume=data["amount"],
					symbol=data["symbol"],
					order_made_by=data["order_made_by"],
					order_direction=data["orderDirection"],
				)
			else:
				order_result = exchange.add_order(
					leverage=data["leverage"],
					order_type=data["orderType"],
					volume=data["amount"],
					symbol=data["symbol"],
					order_made_by=data["order_made_by"],
					stop_loss=data["stopLoss"],
					take_profit=data["takeProfit"],
					order_direction=data["orderDirection"],
				)
			
			if isinstance(order_result, tuple):
				order, fees, price_cripto_in_usdt, error = order_result
				status_code = 200 if error is None else 400
			else:
				order = order_result
				error = None
				status_code = 200
				
			if error is not None or status_code != 200:
				return False

			try:
				total_usdt = amount * float(price_cripto_in_usdt)
				fees = float(fees)

				if data["orderDirection"] == "buy":
					margin_used = amount * leverage
					wallet_admin.add_found(
						user_id,
						margin_used - fees,
						symbol_base,
						exchange_id
					)
					wallet_admin.add_found(
						user_id,
						-total_usdt,
						"USDT",
						"general"
					)
				elif data["orderDirection"] == "sell":
					fees_in_usdt = fees * float(price_cripto_in_usdt)
					net_usdt_received = total_usdt - fees_in_usdt
					wallet_admin.add_found(
						user_id,
						net_usdt_received,
						"USDT",
						"general"
					)
					wallet_admin.add_found(
						user_id,
						-amount,
						symbol_base,
						exchange_id
					)
			except Exception as wallet_error:
				logger.error(f"Wallet transaction error: {wallet_error}")
				return False
				
			return True

		else:
			logger.error(f"Invalid trading mode: {trading_mode}")
			return False
			
	except Exception as e:
		logger.error(f"Unhandled error in add_order: {str(e)}")
		return False
