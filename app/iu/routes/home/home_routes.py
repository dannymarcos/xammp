from flask import Blueprint, render_template, session
from flask_login import login_required, current_user
import logging

from app.iu.routes.utils.utils import get_translated_text

home_bp = Blueprint('home', __name__)
logger = logging.getLogger(__name__)

@home_bp.route("/")
@login_required
def home():
    """Home page route"""
    try:
        current_language = session.get('language', 'en')

        return render_template("home.html", current_language=current_language, is_admin=(current_user.role == "admin"))
    except Exception as e:
        logger.error(f"Error in home route: {e}")
        return render_template("home.html", error=str(e), get_translated_text=get_translated_text, is_admin=(current_user.role == "admin"))
