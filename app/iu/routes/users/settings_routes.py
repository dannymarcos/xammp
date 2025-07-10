from flask import Blueprint, render_template, jsonify, request, session
from flask_login import login_required, current_user
import logging
import json

from app.iu.routes.utils.utils import get_translated_text, load_translations

settings_bp = Blueprint('settings', __name__)
logger = logging.getLogger(__name__)

# Load translations
translations = load_translations()

@settings_bp.route("/settings/password", methods=["GET", "POST"])
@login_required
def settings_password_route():
    try:
        return render_template("settings/password.html", get_translated_text=get_translated_text)
    except Exception as e:
        logger.error(f"Error in password settings: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@settings_bp.route("/settings")
@login_required
def settings_route():
    return render_template("under_construction.html", page_name="Settings", get_translated_text=get_translated_text)

@settings_bp.route("/settings/2fa")
@login_required
def settings_2fa_route():
    return render_template("under_construction.html", page_name="Enable 2FA", get_translated_text=get_translated_text)

@settings_bp.route("/change_language", methods=["POST"])
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