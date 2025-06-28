

import json
import logging
import os
import secrets
import time  # Importar time desde la biblioteca estándar de Python
import traceback
from datetime import datetime

# from app.models.shared_models import  ReferralLink, Withdrawal, Strategy, logger

import numpy as np
import pandas as pd
import requests
import telegram
import tensorflow as tf
from dotenv import load_dotenv
from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import (  # Import Flask-Login functions
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import generate_password_hash

from app.Aplicacion import db
from app.models.create_db import db
from app.models.users import User, update_user_bot_status
from app.models.trades import get_all_trades_from_user
from app.models.strategies import get_all_strategies_from_user, Strategy

from app.viewmodels.api.spot.KrakenSpotApiAddOrder import KrakenSpotApiAddOrder
from app.viewmodels.api.spot.KrakenSpotApiGetAccountBalance import (
    KrakenSpotApiGetAccountBalance,
)
from app.viewmodels.services.GetMethodTrading import GetMethodTrading
from app.viewmodels.services.GetSymbolTrading import GetSymbolTrading
from app.viewmodels.services.TradingBotManager import TradingBotManager
from app.viewmodels.api.spot.KrakenSpotAPITicker import KrakenSpotAPI

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# from app.viewmodels.api.kraken.KrakenAPIFutures import KrakenAPIFutures
# from app.viewmodels.api.futures.KrakenFuturesAPI import KrakenFuturesAPI
# from app.viewmodels.api.spot.KrakenSpotAPITicker import KrakenSpotAPI
# from app.viewmodels.api.kraken.KrakenAPISpot import KrakenAPISpot
# from app.viewmodels.api.bingx.BingxExchange import BingxExchange
from app.viewmodels.api.exchange.Exchange import ExchangeFactory
from app.models.referral_link import ReferralLink

#Iniciamos las variables de entorno desde el archivo .env
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME")
API_KEY_KRAKEN = os.getenv("KRAKEN_API_KEY")
API_SECRET_KRAKEN = os.getenv("KRAKEN_API_SECRET")

# Clases
method_instance= GetMethodTrading()
symbol_instance= GetSymbolTrading()

#Modelo IA
def mse(y_true, y_pred):
    return tf.keras.losses.mean_squared_error(y_true, y_pred)
# Ruta relativa al archivo .keras
ruta_modelo = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'Aegis-IA0003.keras')

# Cargar el modelo
modelo = tf.keras.models.load_model(ruta_modelo, custom_objects={'mse': mse})

# Rutas de los archivos de predicciones, tabla Q y log (ajustadas a los nuevos nombres)
ruta_predictions = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'Aegis-IA0003.keras_predictions.npy')
ruta_q_table = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'Aegis-IA0003.keras_q_table.csv')
ruta_trade_log = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'Aegis-IA0003.keras_trade_log.npy')

# Cargar los archivos correspondientes
predictions = np.load(ruta_predictions)
q_table = pd.read_csv(ruta_q_table)
trade_log = np.load(ruta_trade_log)


# Load translations
def load_translations():
    try:
        with open('translations.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading translations: {e}")
        return {}

translations = load_translations()

def get_translated_text(key, language='en'):
    """Get translated text based on current language"""
    try:
        return translations.get(language, {}).get(key, translations['en'].get(key, key))
    except Exception as e:
        logger.error(f"Error getting translation for {key}: {e}")
        return key

routes_bp = Blueprint("routes", __name__)

# Removed manual trading route as per request
# Initialize Telegram Bot with a valid token 

@routes_bp.route("/")
@login_required
def home():
    """Home page route"""
    try:
        # # Get current language from session or default to English
        current_language = session.get('language', 'en')
        # # Get current user from session
        # user_email = session.get('user_email')
        # if not user_email:
        #     # For testing purposes only
        #     user_email = 'test@example.com'
        #     session['user_email'] = user_email
        
        # user = User.query.filter_by(email=user_email).first()
        # if not user:
        #     # Create test user if it doesn't exist
        #     user = User(
        #         full_name='Test User',
        #         email=user_email,
        #         nationality='Test Country',
        #         phone='+1234567890',
        #         password_hash='test_hash'
        #     )
        #     db.session.add(user)
        #     db.session.commit()
        #     # logger.info("Created test user successfully")
        
        # # Get user's investments total
        # total_invested = db.session.query(db.func.sum(Investment.amount)).filter_by(user_id=user.id).scalar() or 0
        # total_generated = db.session.query(db.func.sum(Investment.total_generated)).filter_by(user_id=user.id).scalar() or 0
        
      
        return render_template("home.html", current_language=current_language, get_translated_text=get_translated_text)
    except Exception as e:
        logger.error(f"Error in home route: {e}")
        return render_template("home.html", error=str(e), get_translated_text=get_translated_text)

@routes_bp.route("/strategies", methods=['GET', 'POST', 'DELETE'])
@login_required
def strategies():
    if request.method == 'GET':
        all_strategies_from_user = get_all_strategies_from_user(current_user.id)
        
        return jsonify({'strategies': all_strategies_from_user})
   
    data = request.get_json()
    if request.method == 'POST':
        text = data.get('text')
        name = data.get('name')
        strategy = Strategy(user_id=current_user.id, text=text, name=name)
        db.session.add(strategy)
        db.session.commit()
        return jsonify({'message': 'Strategy saved successfully'})
    
    if request.method == "DELETE":
        strategy_id = data.get('id')
        strategy = Strategy.query.filter_by(user_id=current_user.id, id=strategy_id).first()
        if strategy:
            db.session.delete(strategy)
            db.session.commit()
            return jsonify({'message': 'Strategy deleted successfully'})
        else:
            return jsonify({'message': 'Strategy not found'}), 404
        
    return jsonify({'message': 'Invalid request method'}), 400

@routes_bp.route("/bot/start_bot_trading", methods=['POST'])
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

        current_bot_status = None
        
        # Validate required parameters
        if not data:
            current_bot_status = "error"
            raise Exception("No JSON data provided in request")
        
        # Get trading mode
        trading_mode = data.get("trading_mode")
        if trading_mode not in ['spot', 'futures']:
            current_bot_status = "error"
            raise Exception(f"Invalid trading mode: {trading_mode}")

        # Create configuration for the bot
        config = {
            'trading_pair': data.get('symbol', 'XBTUSD'),
            'timeframe': data.get('timeframe', '1h'),
            'trade_amount': float(data.get('amount', 0.01)),
            'trading_mode': trading_mode,
            'max_active_trades': data.get('max_active_trades', 1),
            'stop_loss_pct': data.get('stop_loss_pct', 0.02),
            'take_profit_pct': data.get('take_profit_pct', 0.04),
            'strategy_id': selected_strategy_id
        }
        # Initialize the appropriate Kraken API client
        
        name = "bingx" if data.get("exchange") == "bingx" else ("kraken_spot" if trading_mode == "spot" else "kraken_future")
        exchange = ExchangeFactory().create_exchange(name=name, user_id=user_id)
        
        # Start the bot
        if TradingBotManager.start_bot(user_id, exchange, config, bot_id=bot_id):
            # Update bot_status in the database
            current_bot_status = "running"
            update_user_bot_status(user_id, current_bot_status)
            logger.info(f"Bot started successfully for user {user_id}")
            return jsonify({"status": "Bot started", "bot_status": current_bot_status}), 200
        else:
            current_bot_status = "error"
            raise Exception("Failed to start bot")
    
    except Exception as e:
        logger.error(f"Error starting bot for user {current_user.id}: {str(e)}")
        logger.debug(f"Error details: {traceback.format_exc()}")
        current_bot_status = "error"
        update_user_bot_status(current_user.id, current_bot_status)
        return jsonify({"error": str(e), "bot_status": current_bot_status}), 500
    
@routes_bp.route("/bot/stop_bot_trading", methods=['POST'])
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
        current_bot_status = User.query.filter_by(id=user_id).first().bot_status
        
        # Stop the bot (this will need to be adapted for bot_id)
        if TradingBotManager.stop_bot(user_id): # Assuming user_id is still primary key for now
            # Update bot_status in the database
            current_bot_status = "stopped"
            update_user_bot_status(user_id, current_bot_status) # This might also need bot_id
            logger.info(f"Bot {bot_id} stopped successfully for user {user_id}")
            return jsonify({"status": "Bot stopped", "bot_status": current_bot_status}), 200
        else:
            current_bot_status = "error"
            update_user_bot_status(user_id, current_bot_status) # This might also need bot_id
            logger.warning(f"No active bot {bot_id} found for user {user_id}")
            return jsonify({"error": f"No active bot {bot_id} found", "bot_status": current_bot_status}), 404
    
    except Exception as e:
        logger.error(f"Error stopping bot for user {current_user.id}: {str(e)}")
        logger.debug(f"Error details: {traceback.format_exc()}")
        current_bot_status = "error"
        update_user_bot_status(current_user.id, current_bot_status)
        return jsonify({"error": str(e), "bot_status": current_bot_status}), 500
    

@routes_bp.route("/bot/status")
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
        bot_status = user.bot_status
        
        # Check if the bot is actually running
        is_running = TradingBotManager.is_bot_running(user_id)
        
        # If the database says the bot is running but it's not actually running,
        # update the database to reflect the correct status
        if bot_status == "running" and not is_running:
            logger.warning(f"Bot status mismatch for user {user_id}: database says 'running' but bot is not running")
            bot_status = "stopped"
            update_user_bot_status(user_id, bot_status)
        
        logger.debug(f"Bot status for user {user_id}: {bot_status}")
        return jsonify({"bot_status": bot_status, "last_error_message": user.last_error_message or ""}), 200
    
    except Exception as e:
        logger.error(f"Error getting bot status for user {current_user.id}: {str(e)}")
        logger.debug(f"Error details: {traceback.format_exc()}")
        return jsonify({"bot_status": "error", "error": str(e), "last_error_message": user.last_error_message or ""}), 500

@routes_bp.route("/trades")
@login_required
def get_trades():
    """
    Get the trade history for the current user
    
    Returns:
    - 200 OK with the trade history
    - 500 Internal Server Error if an error occurs
    """
    try:
        user_id = current_user.id
        bot_id = request.args.get("bot_id")
        by = request.args.get('by', 'all')
        logger.info("Received get_trades request for bot_id: %s, by: %s from user_id: %s", bot_id, by, user_id)
        # TODO: Implement logic for bot_id

        logger.debug("Getting trade history for user %s, bot %s", user_id, bot_id)

        # Get the trade history from the database (this will need to be adapted for bot_id)
        trades = get_all_trades_from_user(user_id, by) # This might need bot_id

        # Check if the bot is running and get any active trades (this will need to be adapted for bot_id)
        if TradingBotManager.is_bot_running(user_id): # This might need bot_id
            logger.debug("Bot %s is running for user %s, checking for active trades", bot_id, user_id)
            
            # Get the bot instance (this will need to be adapted for bot_id)
            bot = TradingBotManager._bots.get(user_id) # This might need bot_id
            
            # If the bot has active trades, add them to the trade history
            if bot and hasattr(bot, 'active_trades') and bot.active_trades:
                logger.debug("Found %s active trades for user %s", len(bot.active_trades), user_id)
                
                # Convert active trades to the same format as the trade history
                for active_trade in bot.active_trades:
                    # Only add if it's not already in the trade history
                    if not any(t.get('id') == active_trade.get('id') for t in trades):
                        trade_data = {
                            'id': active_trade.get('id', 'unknown'),
                            'by': 'Bot',
                            'timestamp': active_trade.get('time', datetime.now()).isoformat() if isinstance(active_trade.get('time'), datetime) else datetime.now().isoformat(),
                            'order_direction': active_trade.get('side', 'unknown'),
                            'symbol': bot.config.trading_pair if hasattr(bot, 'config') else 'unknown',
                            'price': active_trade.get('price', 0),
                            'volume': bot.config.trade_amount if hasattr(bot, 'config') else 0,
                            'status': 'active'
                        }
                        trades.append(trade_data)
        
        logger.debug("Returning %s trades for user %s", len(trades), user_id)
        return jsonify({"trades": trades}), 200
    
    except Exception as e:
        logger.error("Error getting trades for user %s: %s", current_user.id, str(e))
        logger.debug("Error details: %s", traceback.format_exc())
        return jsonify({"error": str(e), "trades": []}), 500


@routes_bp.route("/finances")
@login_required
def finances_route():
    """Finances page route"""
    try:
#         # Get test user (or current user in production)
#         user = User.query.filter_by(email='test@example.com').first()
#         if not user:
#             return render_template("finances.html", error="User not found",get_translated_text=get_translated_text)
        
#         # Get user's investments
#         investments = Investment.query.filter_by(user_id=user.id).all()
        
#         # Calculate totals
#         total_invested = sum(investment.amount for investment in investments)
#         total_generated = sum(investment.total_generated for investment in investments)
        
#         # Get latest investment for percentages
#         latest_investment = Investment.query.filter_by(user_id=user.id).order_by(Investment.investment_date.desc()).first()
#         daily_percentage = latest_investment.daily_percentage if latest_investment else 0
#         monthly_percentage = latest_investment.monthly_percentage if latest_investment else 0
        
#         # Get withdrawals
#         withdrawals = Withdrawal.query.filter_by(user_id=user.id).all()
        
        # Removed erroneous 'error=str(e)' from try block
        return render_template("finances.html", get_translated_text=get_translated_text) 
#             total_invested=total_invested,
#             total_generated=total_generated,
#             daily_percentage=daily_percentage,
#             monthly_percentage=monthly_percentage,
#             investments=investments,
#             withdrawals=withdrawals,
#             get_translated_text=get_translated_text
#         )
    except Exception as e:
        logger.error(f"Error in finances route: {e}")
        # Use a generic error message instead of potentially undefined 'e'
        return render_template("finances.html", error="An error occurred loading finances.", get_translated_text=get_translated_text)

@routes_bp.route("/request_withdrawal", methods=["POST"])
@login_required
def request_withdrawal():
    """Handle withdrawal requests"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        amount = float(data.get('amount', 0))
        currency = data.get('currency', 'USDT')
        wallet_address = data.get('wallet_address')
        
        if amount <= 0:
            return jsonify({"status": "error", "message": "Invalid withdrawal amount"}), 400
        
        if not wallet_address:
            return jsonify({"status": "error", "message": "Wallet address is required"}), 400
        
        # Validate wallet address format based on currency
        if currency == 'USDT' and not wallet_address.startswith('T'):
            return jsonify({"status": "error", "message": "Invalid USDT (TRC20) wallet address"}), 400
        elif currency == 'BTC' and not (wallet_address.startswith('1') or wallet_address.startswith('3') or wallet_address.startswith('bc1')):
            return jsonify({"status": "error", "message": "Invalid BTC wallet address"}), 400
        
        # # Get test user (or current user in production)
        # user = User.query.filter_by(email='test@example.com').first()
        # if not user:
        #     return jsonify({"status": "error", "message": "User not found"}), 404
            
        # # Calculate total available balance (investments + profits)
        # total_invested = db.session.query(db.func.sum(Investment.amount)).filter_by(user_id=user.id).scalar() or 0
        # total_generated = db.session.query(db.func.sum(Investment.total_generated)).filter_by(user_id=user.id).scalar() or 0
        # total_available = float(total_invested) + float(total_generated)
        
        # Check if withdrawal amount is available
        # if amount > total_available:
        #     return jsonify({
        #         "status": "error",
        #         "message": f"Insufficient funds. Available balance: {total_available} {currency}"
        #     }), 400
        
        # Create withdrawal request
        # withdrawal = Withdrawal(
        #     # user_id=user.id,
        #     amount=amount,
        #     status='pending',
        #     currency=currency,
        #     wallet_address=wallet_address
        # )
        # db.session.add(withdrawal)
        # db.session.commit()
        
        # Redirect to withdrawal confirmation page
        return jsonify({
            "status": "success",
            "message": "Balance verified. Please confirm withdrawal details.",
            "redirect": url_for('routes.confirm_withdrawal', 
                                amount=amount,
                                currency=currency,
                                wallet_address=wallet_address)
        })
    except Exception as e:
        logger.error(f"Error processing withdrawal request: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@routes_bp.route("/confirm_withdrawal")
@login_required
def confirm_withdrawal():
    """Withdrawal confirmation page"""
    try:
        amount = request.args.get('amount')
        currency = request.args.get('currency')
        wallet_address = request.args.get('wallet_address')
        
        if not all([amount, currency, wallet_address]):
            return redirect(url_for('routes.finances_route'))
        
        user = User.query.filter_by(email='test@example.com').first()
        if not user:
            return redirect(url_for('routes.finances_route'))
            
        return render_template('confirm_withdrawal.html',
            amount=amount,
            currency=currency,
            wallet_address=wallet_address,
            # user=user
        )
    except Exception as e:
        logger.error(f"Error displaying withdrawal confirmation: {e}")
        return redirect(url_for('routes.finances_route'))

# Email functionality for withdrawal requests
def send_withdrawal_email(user, amount, currency, wallet_address):
    """Send an email notification for a withdrawal request."""
    # try:
        # msg = MIMEText(f"""
        # Withdrawal Request Details:
        
        # Full Name: {user.full_name}
        # Email: {user.email}
        # Phone: {user.phone}
        # Amount: {amount} {currency}
        # Currency: {currency}
        # Wallet Address: {wallet_address}
        # """)
        
        # msg['Subject'] = 'New Withdrawal Request'
        # msg['From'] = 'noreply@aegis-ia.com'
        # msg['To'] = 'aegisiaapp@gmail.com'
        
        # smtp_server = "smtp.gmail.com"
        # smtp_port = 587
        # smtp_username = os.environ.get('SMTP_USERNAME')
        # smtp_password = os.environ.get('SMTP_PASSWORD')
        
        # with smtplib.SMTP(smtp_server, smtp_port) as server:
        #     server.starttls()
        #     server.login(smtp_username, smtp_password)
        #     server.send_message(msg)
            
        # logger.info(f"Withdrawal email sent for {user.email} - Amount: {amount} {currency}, Wallet: {wallet_address}")
    # except Exception as e:
    #     logger.error(f"Error sending withdrawal email: {e}")


@routes_bp.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            data = request.json

            if not data:
                return jsonify({"error": "Invalid or missing JSON data"}), 400

            email = data.get('email')
            password = data.get('password')
            full_name = data.get('full_name')

            if not email or not password or not full_name:
                 return jsonify({"error": "Missing required fields (email, password, full_name)"}), 400
            
            # Check if email already exists
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                return jsonify({"error": "Email already exists"}), 400

            # Hash the password before storing
            hashed_password = generate_password_hash(password)

            user = User(email=email, password_hash=hashed_password, full_name=full_name)
            db.session.add(user)
            db.session.commit()

            logger.info(f"New user registered: {email}")
            return jsonify({"status": "success", "message": "Registration successful"})

        except Exception as e:
            db.session.rollback() # Rollback in case of error
            logger.error(f"Error registering user: {e}")
            # Return a generic error for the user
            return jsonify({"error": "An internal error occurred during registration"}), 500

    # Render the registration template for GET requests
    return render_template('register.html')

@routes_bp.route("/login", methods=['GET', 'POST'])
def login():
    # Redirect authenticated users away from the login page
    if current_user.is_authenticated:
         return redirect("/")

    if request.method == 'POST':
        try:
            data = request.json

            if not data:
                 data = request.form # Use form data as fallback

            email = data.get('email')
            password = data.get('password')

            if not email or not password:
                return jsonify({
                    "status": "error",
                    "message": "Email and password are required",
                    "error": "Missing required fields (email, password)"
                }), 400

            # Buscar usuario en la base de datos by email
            user = User.query.filter_by(email=email).first()

            # Check if user exists AND the password is correct (using the check_password method)
            if user is None or not user.check_password(password):
                return jsonify({
                    "status": "error",
                    "message": "Invalid credentials",
                    "error": "Invalid email or password"
                }), 401

            # Login exitoso - Use Flask-Login to manage the session
            login_user(user) # Log the user in
            logger.info(f"User {user.email} logged in successfully.")

            # Return success and a redirect URL (frontend handles redirection)
            return jsonify({
                "status": "success",
                "message": "Login successful",
                "redirect": "/" # Or wherever you want to redirect after login
            })

        except Exception as e:
            # No db writes happened here usually, rollback is less critical but good practice
            db.session.rollback()
            logger.error(f"Error during login: {e}")
            # Return a generic error message
            return jsonify({
                "status": "error",
                "message": "An internal server error occurred",
                "error": str(e)
            }), 500

    # Render the login template for GET requests
    return render_template("login.html")

@routes_bp.route("/logout")
@login_required  # Ensure only logged-in users can logout
def logout():
    """Log the user out."""
    user_email = current_user.email # Get email before logging out
    logout_user()
    logger.info(f"User {user_email} logged out successfully.")
    # Redirect to login page after logout
    return redirect(url_for('routes.login'))

# Initialize Telegram bot
if TELEGRAM_BOT_TOKEN:
    bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
    TELEGRAM_BOT_LINK = f"https://t.me/{TELEGRAM_BOT_USERNAME}?start=welcome"
    TELEGRAM_START_COMMAND = '/start'
    TELEGRAM_WELCOME_MESSAGE = (
        "🛡️ ¡Bienvenido al Soporte de Aegis-IA!\n\n"
        "Por favor, selecciona una opción:\n\n"
        "1️⃣ Problemas técnicos\n"
        "2️⃣ Problemas con inversiones\n" 
        "3️⃣ Problemas con retiros\n"
        "4️⃣ Otros problemas\n\n"
        "O escribe tu consulta directamente y nuestro equipo te ayudará lo antes posible.\n\n"
        "🔒 Seguridad & Desarrollo\n"
        "⏰ Tiempo de respuesta: 24 horas"
    )

@routes_bp.route("/submit_support_request", methods=["POST"])
def submit_support_request():
    """Handle support request submission"""
    try:
        data = request.get_json()
        user = User.query.filter_by(email='test@example.com').first()
        
        if not user:
            return jsonify({"status": "error", "message": "User not logged in"}), 401
        
        # Format support ticket message with user info
        ticket_message = (
            f"{TELEGRAM_WELCOME_MESSAGE}\n\n"
            f"Información del usuario:\n"
            f"Nombre: {user.full_name}\n"
            f"Tipo de problema: {data.get('issue_type', 'No especificado')}\n"
            f"Descripción: {data.get('description', 'Sin descripción')}\n\n"
            f"🔒 Seguridad & Desarrollo\n"
            f"⏰ {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Format support ticket message with Aegis-IA logo and shield
        ticket_message = (
            f"🛡️ AEGIS-IA SUPPORT SYSTEM\n\n"
            f"Welcome to Aegis-IA Support!\n"
            f"Your security and development partner.\n\n"
            f"Please use the following commands:\n"
            f"/name - Enter your name\n"
            f"/issue - Describe your issue\n"
            f"/status - Check ticket status\n\n"
            f"Pre-filled information:\n"
            f"Name: {user.full_name}\n"
            f"Issue Type: {data.get('issue_type', 'Not specified')}\n"
            f"Description: {data.get('description', 'No description provided')}\n\n"
            f"🔒 Security & Development\n"
            f"⏰ {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Return direct bot link
        return jsonify({
            "status": "success",
            "message": "Support ticket submitted successfully",
            "telegram_link": TELEGRAM_BOT_LINK,
            "open_in_new_window": True
        })
    except Exception as e:
        logger.error(f"Error submitting support request: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
        
@routes_bp.route("/settings/password", methods=["GET", "POST"])
@login_required
def settings_password_route():
    """Settings password page route"""
    try:
        # if request.method == "POST":
        #     data = request.get_json()
        #     user = User.query.filter_by(email='test@example.com').first()
            
        #     if not user:
        #         return jsonify({"status": "error", "message": "User not found"}), 404
                
        #     current_password = data.get('current_password')
        #     new_password = data.get('new_password')
            
        #     if not current_password or not new_password:
        #         return jsonify({"status": "error", "message": "Missing password data"}), 400
                
        #     if user.password_hash != current_password:  # In production, use proper password verification
        #         return jsonify({"status": "error", "message": "Current password is incorrect"}), 400
                
        #     user.password_hash = generate_password_hash(new_password)
        #     db.session.commit()
            
        #     return jsonify({
        #         "status": "success",
        #         "message": "Password updated successfully"
        #     })
            
        return render_template("settings/password.html",get_translated_text=get_translated_text)
        
    except Exception as e:
        logger.error(f"Error in password settings: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@routes_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile_route():
    """Profile page route"""
    # try:
    #     # Get or create test user
    #     user = User.query.filter_by(email='test@example.com').first()
    #     if not user:
    #         user = User(
    #             full_name='Test User',
    #             email='test@example.com',
    #             nationality='Test Country',
    #             phone='+1234567890',
    #             password_hash='test_hash'
    #         )
    #         db.session.add(user)
    #         db.session.commit()
    #         # logger.info("Created test user successfully")

    #     if request.method == "POST":
    try:
    #             data = request.form
    #             # Update user information
    #             user.full_name = data.get('full_name', user.full_name)
    #             user.nationality = data.get('nationality', user.nationality)
    #             user.phone = data.get('phone', user.phone)
                
    #             # Handle email change
    #             new_email = data.get('email')
    #             if new_email and new_email != user.email:
    #                 # Check if email is already taken
    #                 if User.query.filter_by(email=new_email).first():
    #                     return jsonify({"status": "error", "message": "Email already in use"}), 400
    #                 user.email = new_email
                
    #             # Handle password change
    #             current_password = data.get('current_password')
    #             new_password = data.get('new_password')
    #             if current_password and new_password:
    #                 if user.password_hash == current_password:  # In production, use proper password verification
    #                     user.password_hash = generate_password_hash(new_password)
    #                 else:
    #                     return jsonify({"status": "error", "message": "Current password is incorrect"}), 400
                
    #             db.session.commit()
    #             return jsonify({
    #                 "status": "success",
    #                 "message": "Profile updated successfully",
    #                 "user": {
    #                     "full_name": user.full_name,
    #                     "email": user.email,
    #                     "nationality": user.nationality,
    #                     "phone": user.phone
    #                 }
    #             })
    #         except Exception as e:
    #             logger.error(f"Error updating profile: {e}")
    #             return jsonify({"status": "error", "message": str(e)}), 500
        
        return render_template("profile.html",get_translated_text=get_translated_text)
        
    except Exception as e:
        logger.error(f"Error in profile route: {e}")
        return render_template("profile.html", error="Error loading profile",get_translated_text=get_translated_text)

@routes_bp.route("/update_profile", methods=["POST"])
def update_profile():
    """Update user profile"""
    try:
        data = request.get_json()
        # TODO: Update user data in database
        # For now, just return success
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        return jsonify({"error": str(e)}), 500

@routes_bp.route("/settings")
@login_required
def settings_route():
    """Settings page route"""
    return render_template("under_construction.html", page_name="Settings",get_translated_text=get_translated_text)

@routes_bp.route("/classes")
@login_required
def classes_route():
    """Classes page route"""
    try:
    #     # Get test user (admin)
    #     user = User.query.filter_by(email='test@example.com').first()
    #     is_admin = bool(user)  # For now, test user is admin
        return render_template("classes.html",get_translated_text=get_translated_text)
    except Exception as e:
        logger.error(f"Error in classes route: {e}")
        return render_template("classes.html", error="Error loading classes",get_translated_text=get_translated_text)

@routes_bp.route("/settings/2fa")
@login_required
def settings_2fa_route():
    """Settings 2FA page route"""
    return render_template("under_construction.html", page_name="Enable 2FA",get_translated_text=get_translated_text)

@routes_bp.route("/change_language", methods=["POST"])
def change_language():
    """Change the application language."""
    try:
        data = request.get_json()
        language = data.get('language')
        confirm = data.get('confirm', False)
        
        if not confirm:
            # Return confirmation message in the target language
            confirmation_messages = {
                'en': 'Do you want to change the language to English?',
                'es': '¿Desea cambiar el idioma a Español?',
                'pt': 'Deseja mudar o idioma para Português?',
                'fr': 'Voulez-vous changer la langue en Français?'
            }
            return jsonify({
                "status": "confirm",
                "message": confirmation_messages.get(language, confirmation_messages['en'])
            })
        
        if language not in ['es', 'en', 'pt', 'fr']:
            return jsonify({"error": "Invalid language"}), 400
            
        session['language'] = language
        
        # Load translations for the selected language
        current_translations = translations.get(language, {})
        
        # Update all text elements with translations
        return jsonify({
            "status": "success",
            "translations": current_translations,
            "message": f"Language changed to {language}"
        })
    except Exception as e:
        logger.error(f"Error changing language: {e}")
        return jsonify({"error": str(e)}), 500
    
@routes_bp.route("/get_account_balance", methods =["POST"])
@login_required
def get_account_balance():
    """Get account balance"""
    try:
        # Verificar si la solicitud tiene un cuerpo JSON válido
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        
        # Obtener los datos del cuerpo de la solicitud
        data = request.get_json()
        trading_mode = data.get("trading_mode")
        exchange_name = data.get("exchange_name") # it is the same trading_mode but we are migrating to exchange_name [spot and futures name is for kraken]
        
        # Mapeo de nombres de exchange y sus configuraciones
        exchange_config = {
            "spot": {
                "handler": KrakenSpotApiGetAccountBalance(),
                "special_case": True
            },
            "futures": {
                "factory_name": "kraken_future",
                "error_status": 500
            },
            "bingx-spot": {
                "factory_name": "bingx",
                "error_status": 400
            },
            "bingx-futures": {
                "factory_name": "bingx",
                "trading_mode": "swap",
                "error_status": 400
            }
        }

        # Manejar caso especial de Kraken Spot
        if exchange_name == "spot":
            balance_data = exchange_config["spot"]["handler"].get_account_balance(
                API_KEY_KRAKEN, API_SECRET_KRAKEN
            )
            return jsonify(balance_data)

        # Manejar otros exchanges
        if exchange_name in exchange_config:
            config = exchange_config[exchange_name]
            
            # Crear instancia del exchange
            factory_args = {"name": config["factory_name"], "user_id": current_user.id, "trading_mode": "spot"}
            if "trading_mode" in config:
                factory_args["trading_mode"] = config["trading_mode"]
            
            print(factory_args)
            exchange = ExchangeFactory().create_exchange(
                name=factory_args["name"],
                user_id=factory_args["user_id"],
                trading_mode=factory_args["trading_mode"]
            )
            
            balance = exchange.get_account_balance()
            
            # Manejo de errores
            if "error" in balance:
                error_msg = balance["error"] if exchange_name == "futures" else balance
                logger.error(f"🙃 Error getting account balance: {error_msg}")
                return jsonify(balance), config["error_status"]
            
            return jsonify({"balance": balance})

        # Manejar modos inválidos
        return jsonify({"error": "Invalid trading mode. Use 'spot' or 'futures'"}), 400
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# Obtener metodo de trading por defecto
@routes_bp.route("/get_method_trading")
@login_required
def get_method_trading():
    """Get methos of trading"""
    try:
        trading_mode = method_instance.get_method()

        return jsonify({"method": trading_mode})
    except Exception as e:
        logger.error(f"Error getting cryptocurrencies: {e}")
        return jsonify({"error": str(e)}), 500
    

@routes_bp.route("/get_symbol_trading")
@login_required
def get_symbol_trading():
    """Get symbol of trading"""

    try:
        symbol = symbol_instance.get_symbol()

        return jsonify({"symbol": symbol})
    except Exception as e:
        logger.error(f"Error getting cryptocurrencies: {e}")
        return jsonify({"error": str(e)}), 500

# Configuración específica para cada exchange
exchange_config = {
    "futures": {
        "factory_name": "kraken_future",
        "trading_mode": None,
        "requires_ticker": True
    },
    "spot": {
        "factory_name": "kraken_spot",
        "trading_mode": None,
        "requires_ticker": True
    },
    "bingx-spot": {
        "factory_name": "bingx",
        "trading_mode": None,
        "requires_ticker": False
    },
    "bingx-futures": {
        "factory_name": "bingx",
        "trading_mode": "swap",
        "requires_ticker": False
    }
}

@routes_bp.route("/get_cryptos", methods=['POST'])
@login_required
def get_cryptos():
    """Get available cryptocurrencies"""
    try:
        data = request.get_json()
        exchange_name = data.get("exchange_name")

        # Mapeo para el factory y el trading_mode
        factory_map = {
            "futures":      {"name": "kraken_future", "trading_mode": None},
            "spot":         {"name": "kraken_spot",   "trading_mode": None},
            "bingx-spot":   {"name": "bingx",         "trading_mode": "spot"},
            "bingx-futures":{"name": "bingx",         "trading_mode": "swap"},
        }

        if exchange_name not in factory_map:
            return jsonify({"error": "Invalid exchange name"}), 400

        factory_args = {
            "name": factory_map[exchange_name]["name"],
            "user_id": current_user.id
        }
        if factory_map[exchange_name]["trading_mode"]:
            factory_args["trading_mode"] = factory_map[exchange_name]["trading_mode"]

        exchange = None

        if exchange_name != "spot":
            exchange = ExchangeFactory().create_exchange(**factory_args)

        # Lógica para cada tipo de exchange
        if exchange_name == "futures":
            # Kraken Futures
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
            data, status = spot_client.get_ticker_kraken()
            if status != 200:
                logger.error(f"Spot ticker error: {data}")
                return jsonify(data), status
            
            cryptos, status = spot_client.get_symbol_and_ultimate_price_trade()
            
            if status != 200:
                logger.error(f"Spot symbols error: {cryptos}")
                return jsonify(cryptos), status

            return jsonify(cryptos)

            # Kraken Spot in future
            # if hasattr(exchange, "get_symbol_and_ultimate_price_trade"):
            #     cryptos, status = exchange.get_symbol_and_ultimate_price_trade()
            #     if status != 200:
            #         logger.error(f"Spot symbols error: {cryptos}")
            #         return jsonify(cryptos), status
            #     return jsonify({"cryptos": cryptos})
            # else:
            #     return jsonify({"error": "Not supported"}), 500

        elif exchange_name in ["bingx-spot", "bingx-futures"]:
            # BingX Spot o Futures
            cryptos, err = exchange.get_cryptos()
            if err:
                logger.error(f"Bingx ticker error: {cryptos}")
                return jsonify({"error": f"Bingx ticker error: {cryptos}"}), 400
            return jsonify({"cryptos": cryptos})

        return jsonify({"error": "Invalid trading mode"}), 400

    except Exception as e:
        logger.error(f"Error getting cryptocurrencies: {e}")
        return jsonify({"error": str(e)}), 500

#for single crypto with symbol
@routes_bp.route("/get_symbol_price", methods=['GET'])
@login_required
def get_symbol_price():
    """Get available cryptocurrencies"""
    try:
        symbol = request.args.get('symbol')
        if not symbol:
            return jsonify({"error": "Symbol not provided"}), 400
        
        exchange = request.args.get('exchange')
        if exchange == "futures":
            exchange = ExchangeFactory().create_exchange(name="kraken_future", user_id=current_user.id)
            data = exchange.get_symbol_price(symbol)
            
            return {"price": data[0], "status": data[1]}
        
        elif exchange == "bingx-spot":
            exchange = ExchangeFactory().create_exchange(name="bingx", user_id=current_user.id, trading_mode="spot")
            price, error = exchange.get_symbol_price(symbol)
            if error:
                logger.error(f"Bingx ticker error: {price}")
                return jsonify({"error": f"Bingx ticker error: {price}"}), 400
            
            return jsonify({"price": price , "symbol": symbol})
        
        exchange = ExchangeFactory().create_exchange(name="kraken_spot", user_id=current_user.id)
        data = exchange.get_symbol_price(symbol)
        if data[1] != 200:
            return jsonify(data[0]), data[1]
        
        return jsonify(data[0])

    except Exception as e:
        logger.error(f"Error getting cryptocurrencies: {e}")
        return jsonify({"error": str(e)}), 500

routes_bp.route("/trades", methods=['GET'])
@login_required
def get_user_trades():
    """Get all trades made by the user in the app"""
    try:
        by = request.args.get("by")
        if not current_user.is_authenticated:
            return jsonify({"error": "User not authenticated"}), 401
        
        trades = get_all_trades_from_user(current_user.id, by)
        return jsonify({"trades": trades})

    except Exception as e:
        logger.error(f"Error getting cryptocurrencies: {e}")
        return jsonify({"error": str(e)}), 500
    
@routes_bp.route("/close_order", methods=["POST"])
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


@routes_bp.route("/add_order", methods=["POST"])
@login_required
def add_order():
    """
    Recibe datos desde el front (por fetch) para crear una orden en Kraken.
    Para modo spot, extrae los parámetros necesarios y llama a la clase KrakenSpotApiAddOrder.
    """
    try:
        data = request.get_json()
        trading_mode = data.get("trading_mode")
        user_id = current_user.id

        if trading_mode == "spot":
            # Extraer los parámetros de la orden desde el JSON
            ordertype = data.get("orderType")    # e.g., "limit"
            order_direction = data.get("orderDirection")     # "buy" o "sell"
            volume = data.get("volume")            # volumen en activo base
            symbol = data.get("symbol")            # par de trading, e.g., "XBTUSD"
            price = data.get("price", 0)           # precio de la cripto
            return_all_trades = data.get("return_all_trades", False)
            order_made_by = data.get("order_made_by", "user")
            money_wanted_to_spend = data.get("money_wanted_to_spend")


            # Validar que los parámetros esenciales estén presentes
            if order_direction == "buy":
                required_params = [ordertype, symbol, order_made_by, money_wanted_to_spend]
                if not all(required_params):
                    return jsonify({"error": f"Faltan parámetros requeridos {required_params}"}), 400
            elif order_direction == "sell":
                required_params = [ordertype, order_direction, volume, symbol, order_made_by]
                if not all(required_params):
                    return jsonify({"error": f"Faltan parámetros requeridos {required_params}"}), 400

            # Crear una instancia de la clase para órdenes spot
            exchange = ExchangeFactory().create_exchange(name="kraken_spot", user_id=user_id)

            response = exchange.add_order(ordertype, order_direction, volume, symbol, price, order_made_by, money_wanted_to_spend)

            if return_all_trades:
                all_trades = get_all_trades_from_user(user_id)

            final_res = response[0]
            if return_all_trades:
                final_res["all_trades"] = all_trades
            else:
                final_res["all_trades"] = []

            return jsonify(response[0]), response[1]        
        elif trading_mode in ["futures", "bingx-spot", "bingx-futures"]:
            params = {"user_id": current_user.id}
            
            if trading_mode == "futures":
                params["name"] = "kraken_future"
            elif trading_mode == "bingx-spot":
                params["name"] = "bingx"
            elif trading_mode == "bingx-futures":
                params["name"] = "bingx"
                params["trading_mode"] = "swap"

            exchange = ExchangeFactory().create_exchange(**params)
            # esto es lo que estaba con el kraken_future
            # order, err = exchange.add_order(
            #     order_type=data["orderType"],
            #     order_direction=data["orderDirection"],
            #     volume=data["amount"],
            #     symbol=data["symbol"],
            #     # price=data["entryPrice"], should implement logic to update on db when and order is closed
            #     order_made_by=data["order_made_by"],
            #     take_profit=data["takeProfit"],
            #     stop_loss=data["stopLoss"],
            # )

            order, _ = exchange.add_order(
                leverage=data["leverage"],
                order_type=data["orderType"],
                volume=data["amount"],
                symbol=data["symbol"],
                order_made_by=data["order_made_by"],
                stop_loss=data["stopLoss"],
                take_profit=data["takeProfit"],
                order_direction=data["orderDirection"],
            )

            if "error" in order:
                return jsonify({"error": order["error"], "success": False}), 400
            return jsonify({"order": order, "success": True})
        else:
            return jsonify({"error": f"Modo de trading inválido {trading_mode}"}), 400

    except Exception as e:
        logger.error("Error en add_order: %s", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@routes_bp.route("/upload_class", methods=["POST"])
def upload_class():
    """Handle class video upload"""
    try:
        '''gggg'''
    #     # Check if user is admin
    #     user = User.query.filter_by(email='test@example.com').first()
    #     if not user:
    #         return jsonify({"status": "error", "message": "Unauthorized"}), 401

    #     title = request.form.get('title')
    #     description = request.form.get('description')
    #     video = request.files.get('video')

    #     if not all([title, description, video]):
    #         return jsonify({"status": "error", "message": "Missing required fields"}), 400

    #     # Save video file
    #     filename = secure_filename(video.filename)
    #     video_path = os.path.join('static', 'uploads', filename)
    #     video.save(video_path)

    #     # Save to database
    #     sql = """
    #         INSERT INTO teleclasses (title, description, video_url)
    #         VALUES (?, ?, ?)
    #     """
    #     db.session.execute(sql, [title, description, video_path])
    #     db.session.commit()

    #     return jsonify({"status": "success", "message": "Class uploaded successfully"})
    except Exception as e:
        logger.error(f"Error uploading class: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@routes_bp.route("/generate_access_link", methods=["POST"])
def generate_access_link():
    """Generate access link for teleclasses"""
    try:
        data = request.form
        description = data.get('description')
        expiry = data.get('expiry')
        
        if not description:
            return jsonify({"status": "error", "message": "Description is required"}), 400
            
        # Generate unique access code
        access_code = secrets.token_urlsafe(16)
        
        # Save to database
        sql = """
            INSERT INTO teleclass_access (access_code, description, expiry_date)
            VALUES (?, ?, ?)
        """
        db.session.execute(sql, [access_code, description, expiry])
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "access_link": f"https://aegis-ia.com/teleclasses/{access_code}"
        })
    except Exception as e:
        logger.error(f"Error generating access link: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@routes_bp.route("/generate_referral_link", methods=["GET"])
@login_required
def generate_referral_link():
    """Generate referral link for current user and get referral tree"""
    try:
        # Get current user
        user = User.query.filter_by(id=current_user.id).first()
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404

        # Check if user already has a referral link
        existing_link = ReferralLink.query.filter_by(user_id=user.id, active=True).first()
        if existing_link:
            referral_code = existing_link.code
        else:
            # Generate new referral link
            total_referrals = ReferralLink.query.filter_by(active=False).count()
            referral_number = str(total_referrals + 1).zfill(2)
            referral_code = f"linkreferidosaegiaiaapp{referral_number}"

            # Save to database
            new_link = ReferralLink(
                user_id=user.id,
                code=referral_code,
                active=True
            )
            db.session.add(new_link)
            db.session.commit()

        # Get direct referrals
        direct_referrals = []
        direct_refs = ReferralLink.query.filter_by(referred_by=user.id, active=False).all()
        for ref in direct_refs:
            ref_user = User.query.get(ref.user_id)
            if ref_user:
                direct_referrals.append({
                    "name": ref_user.full_name,
                    "date": ref.used_at.strftime("%Y-%m-%d") if ref.used_at else "N/A"
                })

        # Get indirect referrals (referrals of referrals)
        indirect_referrals = []
        for direct_ref in direct_refs:
            indirect_refs = ReferralLink.query.filter_by(referred_by=direct_ref.user_id, active=False).all()
            for ref in indirect_refs:
                ref_user = User.query.get(ref.user_id)
                referrer = User.query.get(direct_ref.user_id)
                if ref_user and referrer:
                    indirect_referrals.append({
                        "name": ref_user.full_name,
                        "date": ref.used_at.strftime("%Y-%m-%d") if ref.used_at else "N/A",
                        "referred_by": referrer.full_name
                    })

        # Calculate total referrals
        total_referrals = len(direct_referrals) + len(indirect_referrals)

        return jsonify({
            "status": "success",
            "referral_link": referral_code,
            "direct_referrals": direct_referrals,
            "indirect_referrals": indirect_referrals,
            "total_referrals": total_referrals
        })
    except Exception as e:
        logger.error(f"Error generating referral link: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@routes_bp.route("/request_teleclass_access", methods=["POST"])
def request_teleclass_access():
    """Handle teleclass access requests"""
    # try:
    #     data = request.get_json()
    #     if not data or not data.get('reason'):
    #         return jsonify({"status": "error", "message": "Please provide a reason for your request"}), 400

    #     # Get current user
    #     user = User.query.filter_by(email='test@example.com').first()
    #     if not user:
    #         return jsonify({"status": "error", "message": "User not found"}), 404

    #     # Save access request to database
    #     sql = """
    #         INSERT INTO teleclass_requests (user_id, reason, status)
    #         VALUES (?, ?, 'pending')
    #     """
    #     db.session.execute(sql, [user.id, data['reason']])
    #     db.session.commit()

    #     # Send notification to admin (you can implement email notification here)
    #     # logger.info(f"New teleclass access request from {user.email}: {data['reason']}")

    #     return jsonify({
    #         "status": "success",
    #         "message": "Your request has been submitted successfully"
    #     })
    # except Exception as e:
    #     logger.error(f"Error submitting teleclass access request: {e}")
    #     return jsonify({"status": "error", "message": str(e)}), 500

@routes_bp.route("/settings/wallet", methods=["GET", "POST"])
@login_required
def settings_wallet_route():
    """Settings wallet page route"""
    try:
    #     if request.method == "POST":
    #         data = request.form
    #         user = User.query.filter_by(email='test@example.com').first()
    #         if not user:
    #             return jsonify({"status": "error", "message": "User not found"}), 404
                
    #         # Verify current password
    #         if not data.get('current_password'):
    #             return jsonify({"status": "error", "message": "Current password is required"}), 400
                
    #         if user.password_hash != data.get('current_password'):  # In production, use proper password verification
    #             return jsonify({"status": "error", "message": "Current password is incorrect"}), 400
                
    #         # Update wallet address
    #         user.wallet_address = data.get('wallet_address')
    #         db.session.commit()
            
    #         return jsonify({
    #             "status": "success",
    #             "message": "Wallet address updated successfully"
    #         })
            
    #     # GET request - render wallet settings page
    #     user = User.query.filter_by(email='test@example.com').first()
        # Use current_user from Flask-Login instead of undefined 'user'
        return render_template("settings/wallet.html", user=current_user, get_translated_text=get_translated_text) 
        
    except Exception as e:
        logger.error(f"Error in wallet settings: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@routes_bp.route("/get_current_symbol", methods=["GET"])
def get_current_symbol():
    """Get current trading symbol"""
    try:
        # Agregar mensajes de depuración
        print("Intentando acceder a current_symbol.txt")
        
        # Verificar si el archivo existe
        if os.path.exists("current_symbol.txt"):
            with open("current_symbol.txt", "r") as f:
                symbol = f.read().strip()
                print(f"Símbolo leído del archivo: {symbol}")
        else:
            print("El archivo current_symbol.txt no existe. Usando símbolo por defecto")
            # Símbolo por defecto
            symbol = "BTCUSD"

        return jsonify({"symbol": symbol})
    except Exception as e:
        print(f"Error al obtener el símbolo actual: {e}")
        return jsonify({"error": str(e)}), 500

@routes_bp.route("/update_current_symbol", methods=["POST"])
def update_current_symbol():
    """Update current trading symbol"""
    try:
        data = request.get_json()
        new_symbol = data.get("symbol")

        # Guardar el símbolo en un archivo o base de datos en el servidor
        with open("current_symbol.txt", "w") as f:
            f.write(new_symbol)

        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Error updating current symbol: {e}")
        return jsonify({"error": str(e)}), 500
    

@routes_bp.route("/fetch_historical_data")
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
