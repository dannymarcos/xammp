#proyecto_aegisia_main/main.py

import logging
import sys
from app.Aplicacion import Application
from app.config import Config
from app.viewmodels.services.llm import download_model, MODEL_PATHS

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
    if Config().ENVIRONMENT != "local":
        # Descargar los modelos
        download_model(
            MODEL_PATHS["qwen"]["repo_id"],
            MODEL_PATHS["qwen"]["file_name"],
            MODEL_PATHS["qwen"]["dest_dir"]
        )

    download_model(
        MODEL_PATHS["ppo_agent"]["repo_id"],
        MODEL_PATHS["ppo_agent"]["file_name"],
        MODEL_PATHS["ppo_agent"]["dest_dir"]
    )

    from app.iu.routes import routes_bp

    # # Registrar Blueprints si es necesario
    app_instance.register_blueprint(routes_bp)
    try:
        logger.info("Iniciando la inicialización del servidor...")

        app_instance.run()

    except Exception as e:
        logger.error(f"Error al iniciar el servidor: {e}", exc_info=True)
        sys.exit(1)
