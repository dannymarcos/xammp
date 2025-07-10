from flask import Blueprint, jsonify, request
import logging, time, os
from app.models.users import User

support_bp = Blueprint('support', __name__)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME")
TELEGRAM_BOT_LINK = f"https://t.me/{TELEGRAM_BOT_USERNAME}?start=welcome" if TELEGRAM_BOT_USERNAME else None
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

@support_bp.route("/submit_support_request", methods=["POST"])
def submit_support_request():
    try:
        data = request.get_json()
        user = User.query.filter_by(email='test@example.com').first()
        if not user:
            return jsonify({"status": "error", "message": "User not logged in"}), 401
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
        return jsonify({
            "status": "success",
            "message": "Support ticket submitted successfully",
            "telegram_link": TELEGRAM_BOT_LINK,
            "open_in_new_window": True
        })
    except Exception as e:
        logger.error(f"Error submitting support request: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500 