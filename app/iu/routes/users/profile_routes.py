from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
import logging

from app.iu.routes.utils.utils import get_translated_text

profile_bp = Blueprint('profile', __name__)
logger = logging.getLogger(__name__)

@profile_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile_route():
    try:
        return render_template("profile.html", get_translated_text=get_translated_text)
    except Exception as e:
        logger.error(f"Error in profile route: {e}")
        return render_template("profile.html", error="Error loading profile", get_translated_text=get_translated_text)

@profile_bp.route("/update_profile", methods=["POST"])
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
