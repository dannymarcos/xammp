

import os
from flask import current_app, session, jsonify, request, Blueprint, render_template, url_for, redirect
from werkzeug.utils import secure_filename
# from app.models.shared_models import  ReferralLink, Withdrawal, Strategy, logger
from email.mime.text import MIMEText
import secrets
import time # Importar time desde la biblioteca estándar de Python
import smtplib  # For sending emails
import telegram
from werkzeug.security import generate_password_hash
from app.viewmodels.api.spot.KrakenSpotAPITicker import KrakenSpotAPI
from app.viewmodels.api.futures.KrakenFuturesAPI import KrakenFuturesAPI
from app.viewmodels.api.spot.KrakenSpotApiAddOrder import KrakenSpotApiAddOrder
from app.viewmodels.api.spot.KrakenSpotApiGetAccountBalance import KrakenSpotApiGetAccountBalance
from app.models.users import User
from app.models.create_db import db
from werkzeug.security import check_password_hash
import logging
import requests
import pandas as pd
import json
from app.Aplicacion import db
import numpy as np
import tensorflow as tf
from app.viewmodels.services.GetMethodTrading import GetMethodTrading
from app.viewmodels.services.GetSymbolTrading import GetSymbolTrading
from dotenv import load_dotenv
# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#Iniciamos las variables de entorno desde el archivo .env
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME")
API_KEY_KRAKEN = os.getenv("API_KEY_KRAKEN")
API_SECRET_KRAKEN = os.getenv("API_SECRET_KRAKEN")

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
        
      
        return render_template("home.html", current_language=current_language,get_translated_text=get_translated_text)
    except Exception as e:
        logger.error(f"Error in home route: {e}")
        return render_template("home.html", error=str(e),get_translated_text=get_translated_text)

@routes_bp.route("/finances")
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
        
        return render_template("finances.html", error=str(e),get_translated_text=get_translated_text)
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
        return render_template("finances.html", error=str(e),get_translated_text=get_translated_text)

@routes_bp.route("/request_withdrawal", methods=["POST"])
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


@routes_bp.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            password = request.form.get('password')

            print(f"Datos recibidos - Email: {email}, Password: {password}")

            # Obtener todos los usuarios
            users = User.query.all()
        
            for user in users:
                print(f"Email: {user.email}, Nombre: {user.full_name}, Contraseña Hash: {user.password_hash}")
                print(user.check_password(password))  # Debería devolver True

            if not email or not password:
                return jsonify({
                    "status": "error",
                    "message": "Email y contraseña son requeridos"
                }), 400
            
            # Buscar usuario en la base de datos
            user = User.query.filter_by(email=email).first()

            # Buscar contraseña en la base de datos
           # password2 = User.query.filter_by(password_hash = password).first()

            print(f"User: {user}")
            #print(f"Password: {password2}")

            # print(user.check_password(password))  # Debería devolver True
            
            if not user or not user.check_password(password):
                return jsonify({
                    "status": "error",
                    "message": "Credenciales inválidas"
                }), 401
            
            # Login exitoso
            return jsonify({
                "status": "success",
                "message": "Login exitoso",
                "redirect": "/"
            })
            
        except Exception as e:
            logger.error(f"Error en login: {e}")
            return jsonify({
                "status": "error",
                "message": "Error interno del servidor"
            }), 500
    
    return render_template("login.html")

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
def settings_route():
    """Settings page route"""
    return render_template("under_construction.html", page_name="Settings",get_translated_text=get_translated_text)

@routes_bp.route("/classes")
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
def get_account_balance():
    """Get account balance"""
    try:
        # Verificar si la solicitud tiene un cuerpo JSON válido
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        
        # Obtener los datos del cuerpo de la solicitud
        data = request.get_json()
        trading_mode = data.get("trading_mode")

        # print(f"Estamos dentro de get_accouny_balance y la data es: {data}")

        # logger.info(f"Estamos dentro de routes.py en la funcion get_account_balance Trading mode: {trading_mode}")

        # Verificar si el modo de trading es válido
        if trading_mode not in ["spot", "futures"]:
            return jsonify({"error": "Invalid trading mode. Use 'spot' or 'futures'"}), 400
        
        # Obtener el balance según el modo de trading
        if trading_mode == "spot":
            # Para trading spot. usar KrakenSpotApi
            get_account_balance = KrakenSpotApiGetAccountBalance()
            balance_data = get_account_balance.get_account_balance(API_KEY_KRAKEN, API_SECRET_KRAKEN)
            # print(f"Estamos dentro de routes.py en la funcion get_account_balance respuests de la clase: {jsonify(balance_data)}")
            # print(f"balance_data: {jsonify(balance_data)}")
            # print(f"balance_data: {balance_data}")
            # print(f"balance_data: {status}")
           # Devolver el balance
            return jsonify(balance_data)
        
        elif trading_mode == "futures":
            # Para trading futures, usar KrakenFuturesAPI (si está implementado)
            return jsonify({"error": "Futures trading not implemented yet"}), 501
        
    except Exception as e:
        logger.error(f"Error getting balance: {e}")
        return jsonify({"error": str(e)}), 500


# Obtener metodo de trading por defecto
@routes_bp.route("/get_method_trading")
def get_method_trading():
    """Get methos of trading"""
    try:
        trading_mode = method_instance.get_method()

        return jsonify({"method": trading_mode})
    except Exception as e:
        logger.error(f"Error getting cryptocurrencies: {e}")
        return jsonify({"error": str(e)}), 500
    

@routes_bp.route("/get_symbol_trading")
def get_symbol_trading():
    """Get symbol of trading"""

    try:
        symbol = symbol_instance.get_symbol()

        return jsonify({"symbol": symbol})
    except Exception as e:
        logger.error(f"Error getting cryptocurrencies: {e}")
        return jsonify({"error": str(e)}), 500

@routes_bp.route("/get_cryptos", methods=['POST'])
def get_cryptos():
    """Get available cryptocurrencies"""
    try:
        data = request.get_json()
        # trading_mode = current_app.config.get("TRADING_MODE", "spot")
        trading_mode = data.get("trading_mode")

        # logger.info(f"Estamos dentro de routes.py en la funcion get_cryptos Trading mode: {trading_mode}")
        if trading_mode == "futures":
            # logger.info(f"Estamos dentro de futures en routes.py")
            futures_client = KrakenFuturesAPI()
            data, status = futures_client.get_ticker_kraken()
            if status != 200:
                return jsonify(data), status

            cryptos, status = futures_client.get_symbol_and_markPrice()
            if status != 200:
                return jsonify(cryptos), status
            
        elif trading_mode == "spot":
            # Para trading spot. usar KrakenSpotApi
            spot_client = KrakenSpotAPI()
            data, status = spot_client.get_ticker_kraken()
            if status != 200:
                return jsonify(data), status
            cryptos, status = spot_client.get_symbol_and_ultimate_price_trade()
            if status != 200:
                return jsonify(cryptos), status
            
        return jsonify(cryptos)
    except Exception as e:
        logger.error(f"Error getting cryptocurrencies: {e}")
        return jsonify({"error": str(e)}), 500
    
@routes_bp.route("/add_order", methods=["POST"])
def add_order():
    """
    Recibe datos desde el front (por fetch) para crear una orden en Kraken.
    Para modo spot, extrae los parámetros necesarios y llama a la clase KrakenSpotApiAddOrder.
    """
    try:
        data = request.get_json()
        trading_mode = data.get("trading_mode")
        # logger.info(f"Modo de trading recibido: {trading_mode}")

        if trading_mode == "spot":
            # Extraer los parámetros de la orden desde el JSON
            ordertype = data.get("ordertype")    # e.g., "limit"
            order_direction = data.get("type")     # "buy" o "sell"
            volume = data.get("volume")            # volumen en activo base
            symbol = data.get("symbol")            # par de trading, e.g., "XBTUSD"
            price = data.get("price")              # precio límite (si aplica)

            # Validar que los parámetros esenciales estén presentes
            if not all([ordertype, order_direction, volume, symbol, price]):
                return jsonify({"error": "Faltan parámetros requeridos"}), 400

            # Crear una instancia de la clase para órdenes spot
            spot_client = KrakenSpotApiAddOrder()
            
            # Llamar al método add_order pasando los parámetros y las credenciales (API_KEY_KRAKEN y API_SECRET_KRAKEN)
            result = spot_client.add_order(
                ordertype=ordertype,
                order_type=order_direction,
                volume=volume,
                symbol=symbol,
                price=price,
                api_key=API_KEY_KRAKEN,
                api_secret=API_SECRET_KRAKEN
            )
            return jsonify(result)
        
        elif trading_mode == "futures":
            # Aquí podrías implementar la lógica para futuros o devolver un error si aún no está implementado.
            return jsonify({"error": "Futures mode no implementado"}), 501

        else:
            return jsonify({"error": "Modo de trading inválido"}), 400

    except Exception as e:
        logger.error(f"Error en add_order: {e}")
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
def generate_referral_link():
    """Generate referral link for current user and get referral tree"""
    # try:
    #     # Get current user
    #     user = User.query.filter_by(email='test@example.com').first()
    #     if not user:
    #         return jsonify({"status": "error", "message": "User not found"}), 404

    #     # Check if user already has a referral link
    #     existing_link = ReferralLink.query.filter_by(user_id=user.id, active=True).first()
    #     if existing_link:
    #         referral_code = existing_link.code
    #     else:
    #         # Generate new referral link
    #         total_referrals = ReferralLink.query.filter_by(active=False).count()
    #         referral_number = str(total_referrals + 1).zfill(2)
    #         referral_code = f"linkreferidosaegiaiaapp{referral_number}"

    #         # Save to database
    #         new_link = ReferralLink(
    #             user_id=user.id,
    #             code=referral_code,
    #             active=True
    #         )
    #         db.session.add(new_link)
    #         db.session.commit()

    #     # Get direct referrals
    #     direct_referrals = []
    #     direct_refs = ReferralLink.query.filter_by(referred_by=user.id, active=False).all()
    #     for ref in direct_refs:
    #         ref_user = User.query.get(ref.user_id)
    #         if ref_user:
    #             direct_referrals.append({
    #                 "name": ref_user.full_name,
    #                 "date": ref.used_at.strftime("%Y-%m-%d") if ref.used_at else "N/A"
    #             })

    #     # Get indirect referrals (referrals of referrals)
    #     indirect_referrals = []
    #     for direct_ref in direct_refs:
    #         indirect_refs = ReferralLink.query.filter_by(referred_by=direct_ref.user_id, active=False).all()
    #         for ref in indirect_refs:
    #             ref_user = User.query.get(ref.user_id)
    #             referrer = User.query.get(direct_ref.user_id)
    #             if ref_user and referrer:
    #                 indirect_referrals.append({
    #                     "name": ref_user.full_name,
    #                     "date": ref.used_at.strftime("%Y-%m-%d") if ref.used_at else "N/A",
    #                     "referred_by": referrer.full_name
    #                 })

    #     # Calculate total referrals
    #     total_referrals = len(direct_referrals) + len(indirect_referrals)

    #     return jsonify({
    #         "status": "success",
    #         "referral_link": referral_code,
    #         "direct_referrals": direct_referrals,
    #         "indirect_referrals": indirect_referrals,
    #         "total_referrals": total_referrals
    #     })
    # except Exception as e:
    #     logger.error(f"Error generating referral link: {e}")
    #     return jsonify({"status": "error", "message": str(e)}), 500

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
        return render_template("settings/wallet.html", user=user)
        
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
            print("El archivo current_symbol.txt existe")
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


@routes_bp.route('/predict', methods=['POST'])
def predict():

    try:

        data = request.json

        # Verifica si data es una cadena y conviértela a float
        if isinstance(data, str):
            data = float(data)

        # print(f"Estamos en la funcion predict y el valor que recibe es : {data}")
    # features = data['close']

    # print(f"Estamos en la funcion predict y el valor que recibe en features 1: {features}")
    

    # Convertir las características en un array de numpy
        features = np.array([[float(data)]])
        # print(f"Estamos en la funcion predict y el valor que recibe en features 2: {features}")
   

        # print(f"Features con forma correcta: {features.shape}")
   
   
    # Hacer la predicción
        prediction = modelo.predict(features)
        # print(f"Estamos en la funcion predict y el valor que recibe en prediction: {prediction}")
        # Devolver la predicción en formato JSON
        # print(f"Predicción: {prediction}")
        return jsonify({'prediction': prediction.tolist()})
    except ValueError as e:
        # print(f"Error al convertir los datos: {e}")
        return jsonify({'error': 'Error al convertir los datos', 'details': str(e)}), 400
    except Exception as e:
        # print(f"Error al realizar la predicción: {e}")
        return jsonify({'error': 'Error al realizar la predicción', 'details': str(e)}), 500
