from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash
from app.models.users import User
from app.Aplicacion import db
from app.models.referral_link import ReferralLink
import logging

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

@auth_bp.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            data = request.json

            if not data:
                return jsonify({"error": "Invalid or missing JSON data"}), 400

            email = data.get('email')
            password = data.get('password')
            full_name = data.get('full_name')
            referral_code = data.get('referral_code')

            if not email or not password or not full_name:
                 return jsonify({"error": "Missing required fields (email, password, full_name)"}), 400
            
            # Check if email already exists
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                return jsonify({"error": "Email already exists"}), 400

            # Hash the password before storing
            hashed_password = generate_password_hash(password)

            user = User(email=email, password_hash=hashed_password, full_name=full_name)
            
            # Handle referral code if provided
            if referral_code:
                # Check if the referral code is a valid user ID
                referrer_user = User.query.filter_by(id=referral_code).first()
                if referrer_user:
                    user.referred_by = referrer_user.id
                    logger.info(f"User {email} registered with referral code: {referral_code}")
                else:
                    logger.warning(f"Invalid referral code used: {referral_code}")
            
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
    # Check for referral code in URL parameters
    referral_code = request.args.get('ref')
    referrer_name = None
    
    if referral_code:
        # Check if the referral code is a valid user ID
        referrer = User.query.filter_by(id=referral_code).first()
        if referrer:
            referrer_name = referrer.full_name
    
    return render_template('register.html', referral_code=referral_code, referrer_name=referrer_name)

@auth_bp.route("/login", methods=['GET', 'POST'])
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

@auth_bp.route("/logout")
@login_required
def logout():
    user_email = current_user.email
    logout_user()
    logger.info(f"User {user_email} logged out successfully.")
    return redirect(url_for('auth.login'))
