from flask import Blueprint, render_template, session, redirect, url_for, jsonify
from flask_login import login_required, current_user
import logging

from app.iu.routes.utils.utils import get_translated_text
from app.models.users import User # Import User model for the test
from app.models.create_db import db # Import db for the test

home_bp = Blueprint('home', __name__)
logger = logging.getLogger(__name__)

@home_bp.route("/")
@login_required
def home():
    """Home page route"""
    try:
        current_language = session.get('language', 'en')

        if current_user.role == "admin":
            return redirect(url_for('admin.admin_route'))

        return render_template("home.html", current_language=current_language, is_admin=(current_user.role == "admin"), email=current_user.email)
    except Exception as e:
        logger.error(f"Error in home route: {e}")
        return render_template("home.html", error=str(e), get_translated_text=get_translated_text, is_admin=(current_user.role == "admin"), email=current_user.email)
