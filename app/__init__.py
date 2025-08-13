from .Aplicacion import Application
from .config import Config


def create_app():
    """Create and configure the Flask application."""
    app_instance = Application(Config)
    return app_instance.app
