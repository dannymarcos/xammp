from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
import logging
import secrets
import os
from werkzeug.utils import secure_filename

from app.iu.routes.utils.utils import get_translated_text
from app.models.create_db import db

classes_bp = Blueprint('classes', __name__)
logger = logging.getLogger(__name__)

@classes_bp.route("/classes")
@login_required
def classes_route():
    """Classes page route"""
    try:
        return render_template("classes.html", get_translated_text=get_translated_text)
    except Exception as e:
        logger.error(f"Error in classes route: {e}")
        return render_template("classes.html", error="Error loading classes",get_translated_text=get_translated_text)

@classes_bp.route("/upload_class", methods=["POST"])
def upload_class():
    """Handle class video upload"""
    try:
        # Check if user is admin
        # user = User.query.filter_by(email='test@example.com').first()
        # if not user:
        #     return jsonify({"status": "error", "message": "Unauthorized"}), 401

        title = request.form.get('title')
        description = request.form.get('description')
        video = request.files.get('video')

        if not all([title, description, video]):
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        # Save video file
        filename = secure_filename(video.filename)
        video_path = os.path.join('static', 'uploads', filename)
        video.save(video_path)

        # Save to database
        sql = """
            INSERT INTO teleclasses (title, description, video_url)
            VALUES (?, ?, ?)
        """
        db.session.execute(sql, [title, description, video_path])
        db.session.commit()

        return jsonify({"status": "success", "message": "Class uploaded successfully"})
    except Exception as e:
        logger.error(f"Error uploading class: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@classes_bp.route("/generate_access_link", methods=["POST"])
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

@classes_bp.route("/request_teleclass_access", methods=["POST"])
def request_teleclass_access():
    """Handle teleclass access requests"""
    try:
        data = request.get_json()
        if not data or not data.get('reason'):
            return jsonify({"status": "error", "message": "Please provide a reason for your request"}), 400

        # Get current user
        # user = User.query.filter_by(email='test@example.com').first()
        # if not user:
        #     return jsonify({"status": "error", "message": "User not found"}), 404

        # Save access request to database
        sql = """
            INSERT INTO teleclass_requests (user_id, reason, status)
            VALUES (?, ?, 'pending')
        """
        # db.session.execute(sql, [user.id, data['reason']])
        # db.session.commit()

        # Send notification to admin (you can implement email notification here)
        # logger.info(f"New teleclass access request from {user.email}: {data['reason']}")

        return jsonify({
            "status": "success",
            "message": "Your request has been submitted successfully"
        })
    except Exception as e:
        logger.error(f"Error submitting teleclass access request: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500