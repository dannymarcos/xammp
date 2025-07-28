# Importar todos los blueprints de las secciones
from .wallets.wallet_routes import wallet_bp
from .bots.bot_routes import bot_bp
from .strategies.strategies_routes import strategies_bp
from .users.auth_routes import auth_bp
from .users.profile_routes import profile_bp
from .users.settings_routes import settings_bp
from .finances.finances_routes import finances_bp
from .classes.classes_routes import classes_bp
from .referrals.referrals_routes import referrals_bp
from .supports.support_routes import support_bp
from .tradings.trading_routes import trading_bp
from .home.home_routes import home_bp
from .admin.admin_routes import admin_bp
from .utils.utils import load_translations, get_translated_text
from .see.see import see_bp

# Lista de todos los blueprints para registro masivo
all_blueprints = [
    wallet_bp,
    bot_bp,
    strategies_bp,
    auth_bp,
    profile_bp,
    settings_bp,
    finances_bp,
    classes_bp,
    referrals_bp,
    support_bp,
    trading_bp,
    home_bp,
    admin_bp,
    see_bp
]

def register_blueprints(app):
    """Registra todos los blueprints en la aplicación Flask"""
    for blueprint in all_blueprints:
        app.register_blueprint(blueprint)

__all__ = [
    'wallet_bp',
    'bot_bp', 
    'strategies_bp',
    'auth_bp',
    'profile_bp',
    'settings_bp',
    'finances_bp',
    'classes_bp',
    'referrals_bp',
    'support_bp',
    'trading_bp',
    'all_blueprints',
    'register_blueprints',
    'load_translations',
    'get_translated_text',
    'translations',
    'home_bp',
    'admin_bp',
    'see_bp'
]
