#proyecto_aegisia_main/main.py
import logging
import sys
from flask import Flask
from app.Aplicacion import Application
from app.iu.routes import routes_bp
from app.config import Config

# Configuración del logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app_instance = Application(Config)


if __name__ == "__main__":
    # # Registrar Blueprints si es necesario
    app_instance.register_blueprint(routes_bp)
    try:
        logger.info("Iniciando la inicialización del servidor...")
        
        app_instance.run()
        
    except Exception as e:
        logger.error(f"Error al iniciar el servidor: {e}", exc_info=True)
        sys.exit(1)
