import logging
import flask
from app.viewmodels.api.exchange.Exchange import ExchangeFactory
from app.iu.routes.tradings.trading_routes import get_current_price, validate_master_account_balance
from app.viewmodels.wallet.found import Wallet

logger = logging.getLogger(__name__)

def process_order(user_id: int, data: dict, trading_mode: str) -> tuple[bool, float]:
	wallet = Wallet(user_id=user_id)

	# Ajustar símbolo según trading_mode
	symbol = data.get('symbol')
	symbol_base = symbol.split('/')[0]
	if trading_mode == 'bingx_spot':
		data['symbol'] = symbol.replace(':USDT', '')
	elif trading_mode == 'bingx_futures':
		if ':USDT' not in symbol:
			data['symbol'] = symbol + ':USDT'

	# Preparar parámetros para crear el exchange
	params = { 'user_id': user_id, 'name': 'bingx' }
	if trading_mode == 'bingx_spot':
		params['trading_mode'] = 'spot'
	elif trading_mode == 'bingx_futures':
		params['trading_mode'] = 'swap'

	exchange = ExchangeFactory().create_exchange(**params)
	current_price = get_current_price(exchange, data['symbol'])
	if current_price is None:
		logger.error('Failed to get current price')
		return False, 0.00

	try:
		amount = float(data.get('amount'))
		leverage = float(data.get('leverage'))
	except (TypeError, ValueError):
		logger.error('Invalid amount or leverage')
		return False, 0.00

	price_calc = float(current_price) * amount
	total_cost = price_calc * leverage

	# Validación de saldos
	if data.get('orderDirection') == 'buy':
		if not wallet.has_balance_in_currency(total_cost, 'USDT', 'USDT', 'general'):
			logger.error(f'Insufficient USDT balance: {total_cost}')
			return False, 0.00
		
		is_valid, _ = validate_master_account_balance(price_calc, 'USDT', trading_mode)
		if not is_valid:
			logger.error('Master account USDT balance insufficient')
			return False, 0.00
	elif data.get('orderDirection') == 'sell':
		required_balance = amount * leverage

		if wallet.get_blocked_balance(currency="BTC/USDT", by_bot=data["order_made_by"])["amount_crypto"] < required_balance:
			logger.error(f'Insufficient {symbol_base} balance: {required_balance}')
			return False, 0.00

		if trading_mode == 'bingx_spot':
			is_valid, _ = validate_master_account_balance(required_balance, symbol_base, trading_mode)
			if not is_valid:
				logger.error(f'Master account {symbol_base} balance insufficient')
				return False, 0.00

	# Realizar la orden usando contexto Flask
	if not flask.has_app_context():
		from app.__init__ import create_app
		app = create_app()
		with app.app_context():
			order_result = exchange.add_order(
				leverage=data.get('leverage'),
				order_type=data.get('orderType'),
				volume=data.get('amount'),
				symbol=data.get('symbol'),
				stop_loss=None,
				take_profit=None,
				order_direction=data.get('orderDirection'),
				order_made_by=data.get('order_made_by')
			)
	else:
		order_result = exchange.add_order(
			leverage=data.get('leverage'),
			order_type=data.get('orderType'),
			volume=data.get('amount'),
			symbol=data.get('symbol'),
			stop_loss=None,
			take_profit=None,
			order_direction=data.get('orderDirection'),
			order_made_by=data.get('order_made_by')
		)

	if isinstance(order_result, tuple):
		order, fees, price_cripto_in_usdt, cost_in_usdt, fees_currency, status_code = order_result
	else:
		logger.error('Invalid order result format')
		return False, 0.00

	if status_code != 200:
		return False, 0.00

	try:
		amount_traded = amount * leverage
		cost_in_usdt = float(cost_in_usdt)
		fees = float(fees)
		if data.get('orderDirection') == 'buy':
			# amount_obtained = amount_traded - (fees / float(price_cripto_in_usdt))
			wallet.add_blocked_balance(
				amount_usdt=-(cost_in_usdt - fees),
				amount_crypto=amount_traded,
				currency="BTC/USDT",
				by_bot=data["order_made_by"]
			)
			# handle_user_balance[user_id]['usd'] += -(cost_in_usdt - fees)
			# handle_user_balance[user_id]['cripto'] += amount_traded
		elif data.get('orderDirection') == 'sell':
			# amount_obtained = -amount_traded
			wallet.add_blocked_balance(
				amount_usdt=(cost_in_usdt - fees),
				amount_crypto=-amount_traded,
				currency="BTC/USDT",
				by_bot=data["order_made_by"]
			)
			# handle_user_balance[user_id]['usd'] += (cost_in_usdt - fees)
			# handle_user_balance[user_id]['cripto'] += -amount_traded
		else:
			return False, 0.00
	except Exception as e:
		logger.error(f'Wallet transaction error: {e}')
		return False, 0.00

	return True, amount_traded
