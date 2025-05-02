#proyecto_aegisia_main/app/models/create_db.py

from flask_sqlalchemy import SQLAlchemy 

db = SQLAlchemy()

# Importa todos tus modelos aquí para que Flask-Migrate los detecte
from .users import User
from .trades import Trade