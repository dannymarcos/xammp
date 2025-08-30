import logging
import sys
from app.Aplicacion import Application
from app.config import Config
from app.viewmodels.services.llm import download_model, MODEL_PATHS
from app.iu.routes import register_blueprints
from waitress import serve

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

# Importar y registrar los blueprints refactorizados

# Registrar todos los blueprints
register_blueprints(app_instance.app)

# Exponer la aplicación para Waitress
app = app_instance.app

if __name__ == "__main__":
    # Descargar modelos solo si no están en entorno local
    if Config().ENVIRONMENT != "local":
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
    
    try:
        ip = Config().IP
        port = Config().PORT
        threads = Config().THREADS
        environment = Config().ENVIRONMENT
        connection_limit = Config().CONNECTION_LIMIT
        channel_timeout = Config().CHANNEL_TIMEOUT

        if environment in ["production", "production-ia"]:
            logger.info("Starting Waitress server for production...")
            logger.info("================")
            logger.info(f" PORT              {port}")
            logger.info(f" THREADS           {threads}")
            logger.info(f" CONNECTION LIMIT  {connection_limit}")
            logger.info(f" CHANNEL TIMEOUT   {channel_timeout}")
            logger.info("================")

            serve(
                app, 
                host=ip,
                port=port, 
                threads=threads,
                connection_limit=connection_limit,
                channel_timeout=channel_timeout
            )
        else:
            logger.info("Starting the server in dev mode...")
            app_instance.run(debug=True)
            
    except Exception as e:
        logger.error(f"Error al iniciar el servidor: {e}", exc_info=True)
        sys.exit(1)