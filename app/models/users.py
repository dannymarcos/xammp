# app/models/user.py
from .create_db import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin  # Import UserMixin

class User(db.Model, UserMixin):  # Inherit from UserMixin
    __tablename__ = 'users'

    # Use email as the primary key and ID for Flask-Login
    email = db.Column(db.String(120), unique=True, nullable=False, primary_key=True)
    full_name = db.Column(db.String(255))
    nationality = db.Column(db.String(100))
    password_hash = db.Column(db.String(255), nullable = False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Required by Flask-Login UserMixin
    def get_id(self):
        return str(self.email)
