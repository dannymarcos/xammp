# app/models/user.py
import uuid
from .create_db import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin  # Import UserMixin
from dotenv import load_dotenv # TODO: Remove dotenv
import os
import traceback

load_dotenv()
KRAKEN_API_KEY = os.getenv("KRAKEN_API_KEY")
KRAKEN_API_SECRET = os.getenv("KRAKEN_API_SECRET")

class User(db.Model, UserMixin):  # Inherit from UserMixin
    __tablename__ = 'users'

    # UUID as primary key
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(255))
    nationality = db.Column(db.String(100))
    password_hash = db.Column(db.String(255), nullable=False)
    bot_status = db.Column(db.String(16), nullable=False, default="stopped")
    kraken_api_key = db.Column(db.String(255), default=KRAKEN_API_KEY) # TODOL REMOVE
    kraken_api_secret = db.Column(db.String(255), default=KRAKEN_API_SECRET) # TODOL REMOVE
    last_error_message = db.Column(db.String(255), default="")
    role = db.Column(db.String(16), nullable=False, default="user")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Required by Flask-Login UserMixin
    def get_id(self):
        return str(self.id)


def update_user_bot_status(user_id, bot_status):
    user = User.query.filter_by(id=user_id).first()
    if user:
        user.bot_status = bot_status
        db.session.commit()

def add_last_error_message(user_id, message):
        from main import app_instance
        # limit msg to 255 chars
        if len(message) > 255:
            message = message[:254]

        app = app_instance
        try:
            if hasattr(app, 'app_context'):
                with app.app_context():
                    user = User.query.filter_by(id=user_id).first()
                    if user:
                        user.last_error_message = message
                        db.session.commit()
            else:
                try:
                    user = User.query.filter_by(id=user_id).first()
                    if user:
                        user.last_error_message = message
                        db.session.commit()
                except RuntimeError as e:
                    if 'working outside of application context' in str(e).lower():
                        raise RuntimeError("Flask application context not available")
                    raise
        except Exception:
            traceback.print_exc()
    