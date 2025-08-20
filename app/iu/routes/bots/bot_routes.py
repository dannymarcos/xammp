from app.lib.utils.tx import emit
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
import logging, traceback
from app.models.users import User, update_user_bot_status
from app.viewmodels.services.TradingBotManager import TradingBotManager
from app.viewmodels.api.exchange.Exchange import ExchangeFactory
from app.viewmodels.wallet.found import Wallet

bot_bp = Blueprint('bot', __name__)
logger = logging.getLogger(__name__)

def get_current_price(exchange, symbol):
    asset_price = None

    try:
        current_price = exchange.get_symbol_price(symbol)

        if isinstance(current_price, tuple):
            asset_price = current_price[0]
            if isinstance(asset_price, dict) and "price" in asset_price:
                asset_price = asset_price["price"]
        elif isinstance(current_price, dict) and "price" in current_price:
            asset_price = current_price["price"]
        else:
            asset_price = current_price            
    except Exception as price_error:
        logger.error(f"Error getting current price for {symbol}: {price_error}")

    return asset_price

@bot_bp.route("/bot/start_bot_trading", methods=['POST'])
def start_bot_trading():
    """
    Start a trading bot for the current user
    
    Expects a JSON payload with:
    - bot_id: Identifier for the bot instance
    - symbol: Trading pair (e.g., BTC/USD)
    - timeframe: Chart timeframe (e.g., 1h)
    - amount: Trade amount
    - interval: Trading interval in seconds
    - trading_mode: 'spot' or 'futures'
    
    Returns:
    - 200 OK if bot started successfully
    - 400 Bad Request if invalid parameters or bot already running
    - 500 Internal Server Error if an error occurs
    """
    try:
        data = request.get_json()
        user_id = current_user.id
        bot_id = data.get("bot_id")
        selected_strategy_id = data.get("strategy_id", "")
        logger.info(f"Received start_bot_trading request for bot_id: {bot_id} by user_id: {user_id} and strategy_id: {selected_strategy_id}")
        # TODO: Implement logic for bot_id

        print(request.get_json())

        current_bot_status = None
        
        if bot_id == "strategy-bot" and selected_strategy_id == "":
            emit(email=current_user.email, event="bot", data={"id": bot_id, "msg": "Choose a strategy before starting the bot"})
            raise Exception("Choose a strategy before starting the bot")

        # Validate required parameters
        if not data:
            current_bot_status = "error"
            raise Exception("No JSON data provided in request")
        
        # Get trading mode
        trading_mode = data.get("trading_mode")
        if trading_mode not in ['spot', 'futures']:
            current_bot_status = "error"
            raise Exception(f"Invalid trading mode: {trading_mode}")

        # Validar balance en la wallet del usuario
        trade_amount = float(data.get('amount', 0.01))

        trading_pair = data.get('symbol', 'XBTUSD')

        # Determinar la moneda a usar (ej: USDT para BTC/USDT)        
        quote_currency = trading_pair.split("/")[1] # USDT
        base_currency = trading_pair.split("/")[0] # BTC
        wallet = Wallet(user_id)

        type_exchange: str = data.get("exchange")
        type_exchange_trading_mode: str = type_exchange+"_"+trading_mode
        type_exchange_trading_mode = type_exchange_trading_mode.lower()
        
        if type_exchange == "kraken":
            raise Exception(f"kraken is temporarily disabled for bots")

        if trade_amount < 0.00001 and type_exchange_trading_mode in ["bingx_spot", "kraken_spot"]:
            raise Exception(f"Must be an amount greater than 0.00001")
        elif trade_amount < 0.0001 and type_exchange_trading_mode in ["bingx_futures", "kraken_futures"]:
            raise Exception(f"Must be an amount greater than 0.0001")

        # Permitir tener el symbol correcto para cada caso
        if type_exchange_trading_mode == "kraken_spot":       trading_pair = "BTC/USD"
        elif type_exchange_trading_mode == "kraken_futures":  trading_pair = "BTC/USD:USD"
        elif type_exchange_trading_mode == "bingx_spot":      trading_pair = "BTC/USDT"
        elif type_exchange_trading_mode == "bingx_futures":   trading_pair = "BTC/USDT:USDT"

        # Create configuration for the bot
        config = {
            'trading_pair': trading_pair,
            'timeframe': data.get('timeframe', '1h'),
            'trade_amount': trade_amount,
            'trading_mode': trading_mode,
            'basic_bot_trading_mode_full': type_exchange_trading_mode,
            'max_active_trades': data.get('max_active_trades', 1),
            'stop_loss_pct': data.get('stop_loss_pct', 0.02),
            'take_profit_pct': data.get('take_profit_pct', 0.04),
            'strategy_id': selected_strategy_id
        }

        print("@"*30)
        print(config)
        print("@"*30)
        
        emit(email=current_user.email, event="bot", data={"id": bot_id, "msg": "Start bot"})
        
        name = "bingx" if type_exchange == "bingx" else ("kraken_spot" if trading_mode == "spot" else "kraken_future")

        exchange = ExchangeFactory().create_exchange(name=name, user_id=user_id)
        
        price = get_current_price(exchange, trading_pair)
        if isinstance(price, dict):
            # If price is a dictionary, try to extract the numeric value
            price_value = price.get("price")
            if price_value is None:
                # If no "price" key is found, raise an error
                raise ValueError(f"Invalid price response: {price}. Symbol: {trading_pair}")
            price = price_value
        elif price is None:
            # If price is None, raise an error
            raise ValueError("Invalid price response")

        # Now you can safely perform the multiplication
        amount_in_usdt = trade_amount * price

        quote_currency = "USDT" if quote_currency == "USD" else quote_currency

        if not wallet.has_balance_in_currency(amount_in_usdt, quote_currency, "USDT", "general", name):
            formatted_amount = f"{amount_in_usdt:.10f}".rstrip('0').rstrip('.') if '.' in f"{trade_amount:.10f}" else f"{trade_amount:.10f}"

            emit(email=current_user.email, event="bot", data={"id": bot_id, "msg": f"Insufficient {quote_currency} balance in your general wallet. Required: {formatted_amount}"})
            return jsonify({"error": f"Insufficient {quote_currency} balance in your general wallet. Required: {formatted_amount}"}), 400

        # Start the bot
        if TradingBotManager.start_bot(user_id, exchange, config, bot_id=bot_id, type_wallet=type_exchange_trading_mode, email=current_user.email):
            # Update bot_status in the database
            current_bot_status = "running"
            update_user_bot_status(user_id, current_bot_status, bot_id)
            logger.info(f"Bot started successfully for user {user_id}")
            return jsonify({"status": "Bot started", "bot_status": current_bot_status}), 200
        else:
            current_bot_status = "error"
            emit(email=current_user.email, event="bot", data={"id": bot_id, "msg": "Failed to start bot"})

            raise Exception("Failed to start bot")
    
    except Exception as e:
        logger.error(f"Error starting bot for user {current_user.id}: {str(e)}")
        logger.debug(f"Error details: {traceback.format_exc()}")
        current_bot_status = "error"
        update_user_bot_status(current_user.id, current_bot_status, bot_id)
        traceback.print_exc()
        return jsonify({"error": str(e), "bot_status": current_bot_status}), 500

@bot_bp.route("/bot/stop_bot_trading", methods=['POST'])
@login_required
def stop_bot_trading():
    """
    Stop a trading bot for the current user
    
    Returns:
    - 200 OK if bot stopped successfully
    - 404 Not Found if no active bot found
    - 500 Internal Server Error if an error occurs
    """
    try:
        data = request.get_json()
        user_id = current_user.id
        bot_id = data.get("bot_id")
        logger.info(f"Received stop_bot_trading request for bot_id: {bot_id} by user_id: {user_id}")
        # TODO: Implement logic for bot_id
        
        # Get current bot status (this might need adjustment based on bot_id)
        if bot_id == "strategy_bot":
            current_bot_status = User.query.filter_by(id=user_id).first().strategy_bot_status
        else:
            current_bot_status = User.query.filter_by(id=user_id).first().basic_bot_status
        
        # Stop the bot (this will need to be adapted for bot_id)
        if TradingBotManager.stop_bot(user_id, bot_id): # Assuming user_id is still primary key for now
            # Update bot_status in the database
            current_bot_status = "stopped"
            update_user_bot_status(user_id, current_bot_status, bot_id) # This might also need bot_id
            logger.info(f"Bot {bot_id} stopped successfully for user {user_id}")
            emit(email=current_user.email, event="bot", data={"id": bot_id, "msg": "The bot has been stopped"})
            return jsonify({"status": "Bot stopped", "bot_status": current_bot_status}), 200
        else:
            current_bot_status = "error"
            update_user_bot_status(user_id, current_bot_status, bot_id) # This might also need bot_id
            logger.warning(f"No active bot {bot_id} found for user {user_id}")
            return jsonify({"error": f"No active bot {bot_id} found", "bot_status": current_bot_status}), 404
    
    except Exception as e:
        logger.error(f"Error stopping bot for user {current_user.id}: {str(e)}")
        logger.debug(f"Error details: {traceback.format_exc()}")
        current_bot_status = "error"
        update_user_bot_status(current_user.id, current_bot_status, bot_id)
        return jsonify({"error": str(e), "bot_status": current_bot_status}), 500

@bot_bp.route("/bot/status")
@login_required
def get_bot_status():
    """
    Get the current status of the trading bot for the current user
    
    Returns:
    - 200 OK with the bot status
    - 500 Internal Server Error if an error occurs
    """
    try:
        user_id = current_user.id
        bot_id = request.args.get("bot_id")
        logger.info(f"Received get_bot_status request for bot_id: {bot_id} by user_id: {user_id}")
        # TODO: Implement logic for bot_id

        logger.debug(f"Getting bot status for user {user_id}, bot {bot_id}")
        
        # Get the bot status from the database (this will need to be adapted for bot_id)
        user = User.query.filter_by(id=user_id).first()
        if not user:
            logger.error(f"User {user_id} not found")
            return jsonify({"bot_status": "error"}), 404
        
        # Get the bot status
        strategy_bot_status = user.strategy_bot_status
        basic_bot_status = user.basic_bot_status
        
        # Check if the bot is actually running
        is_running = TradingBotManager.is_bot_running(user_id, bot_id)
        
        # If the database says the bot is running but it's not actually running,
        # update the database to reflect the correct status
        bot_status = strategy_bot_status if bot_id == "strategy-bot" else basic_bot_status

        if bot_status == "running" and not is_running:
            logger.warning(f"Bot status mismatch for user {user_id}: database says 'running' but bot is not running")
            bot_status = "stopped"
            update_user_bot_status(user_id, bot_status, bot_id)
        
        logger.debug(f"Bot status for user {user_id}: {bot_status}")
        return jsonify({"bot_status": bot_status, "last_error_message": user.last_error_message or ""}), 200
    
    except Exception as e:
        logger.error(f"Error getting bot status for user {current_user.id}: {str(e)}")
        logger.debug(f"Error details: {traceback.format_exc()}")
        return jsonify({"bot_status": "error", "error": str(e), "last_error_message": user.last_error_message or ""}), 500
