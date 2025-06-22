# app/config.py
import os
from dotenv import load_dotenv
# Cargar variables de entorno desde .env
load_dotenv()

def get_database_uri():
    """Obtiene la URI de la base de datos con manejo robusto"""
    PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    
    db_uri = os.getenv('SQLALCHEMY_DATABASE_URI')
    
    # Si no esta definida o esta vacía, usar SQLite por defecto
    if not db_uri:
        instance_dir = os.path.join(PROJECT_DIR, 'instance')
        os.makedirs(instance_dir, exist_ok=True)
        db_path = os.path.join(instance_dir, 'your_database.db')
        db_uri = f'sqlite:///{db_path}'
    
    return db_uri

class Config:
    SQLALCHEMY_DATABASE_URI = get_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'una-clave-secreta-muy-dificil')
    TRADING_MODE="spot"
    SYMBOL = "XBTUSD"
