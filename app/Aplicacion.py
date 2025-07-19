#app/Aplicacion.py

#app/Aplicacion.py

from flask import Flask
from flask_cors import CORS
from flask_login import LoginManager  # Import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel, _
import sqlalchemy  # Import Babel and _ function for translations

from app.models.create_db import db
from app.models.users import User  # Import the User model
import os

class Application:
   
    def __init__(self, config_object):
        self.app = Flask(__name__, template_folder="iu/templates", static_folder="iu/static")
        self.app.config.from_object(config_object)
        
        # Set default Babel configuration
        self.app.config['BABEL_DEFAULT_LOCALE'] = 'en'
        self.app.config['BABEL_DEFAULT_TIMEZONE'] = 'UTC'
        
        db.init_app(self.app) #Inicializamos db dentro del constructor
        CORS(self.app)
        
        # Initialize Babel for translations
        self.babel = Babel(self.app)
        
        # Make the _ function available in templates
        self.app.jinja_env.globals['_'] = _

        # Track logged-in users (email: id)
        self.logged_users = {}

        # Initialize Flask-Login
        self.login_manager = LoginManager()
        self.login_manager.init_app(self.app)
        self.login_manager.login_view = 'routes.login'  # Set the login view route (using blueprint name)
        self._register_user_loader() # Register the user loader callback

        self.init_db()

    def init_db(self):
        """Inicializa la base de datos con manejo de errores mejorado"""
        try:
            with self.app.app_context():
                driver_name = db.engine.url.drivername
                
                # Solo para SQLite: crear directorios
                if driver_name == 'sqlite':
                    db_path = db.engine.url.database
                    if db_path and db_path != ':memory:':
                        db_path = os.path.abspath(db_path)
                        db_dir = os.path.dirname(db_path)
                        if db_dir and not os.path.exists(db_dir):
                            os.makedirs(db_dir, exist_ok=True)
                            self.app.logger.info(f"✅ Directorio creado: {db_dir}")

                self.app.logger.info(f"🔍 Conectando a {driver_name}...")
                
                # Verificar conexión (compatible con MySQL)
                with db.engine.connect() as conn:
                    self.app.logger.info(f"✅ Conexión exitosa a {driver_name}")
                    
                    # Crear tablas
                    self.app.logger.info("🛠 Creando estructura de la base de datos...")
                    db.create_all()
                    
                    # Verificar tablas creadas
                    inspector = db.inspect(db.engine)
                    existing_tables = inspector.get_table_names()
                    expected_tables = [cls.__tablename__ for cls in db.Model.__subclasses__()]
                    missing_tables = [t for t in expected_tables if t not in existing_tables]
                    
                    if missing_tables:
                        error_msg = f"❌ Tablas faltantes: {', '.join(missing_tables)}"
                        self.app.logger.error(error_msg)
                        raise RuntimeError(error_msg)
                    
                    self.app.logger.info(f"✅ Base de datos inicializada. Tablas: {', '.join(existing_tables)}")
        
        except sqlalchemy.exc.OperationalError as oe:
            error_msg = f"🚨 Error de conexión ({driver_name}): {str(oe)}"
            self.app.logger.critical(error_msg)
            self.app.logger.critical(f"URI de conexión: {self.app.config['SQLALCHEMY_DATABASE_URI']}")
            raise RuntimeError(error_msg) from oe
            
        except Exception as e:
            error_msg = f"🚨 Error crítico: {str(e)}"
            self.app.logger.exception(error_msg)
            raise RuntimeError(error_msg) from e

    def register_blueprint(self, blueprint):
        self.app.register_blueprint(blueprint)

    def run(self, host='0.0.0.0', port=8080, debug=True, threaded=True):
        self.app.run(host=host, port=port, debug=debug, threaded=threaded)

    def _register_user_loader(self):
        """Register the user_loader callback with Flask-Login."""
        @self.login_manager.user_loader
        def load_user(user_id):
            # Now using UUID string as ID
            return User.query.get(user_id)

    def app_context(self): 
        return self.app.app_context()

    def add_logged_user(self, email, user_id):
        """Add a logged-in user to the storage."""
        self.logged_users[email] = user_id

    def remove_logged_user(self, email):
        """Remove a logged-out user from the storage."""
        if email in self.logged_users:
            del self.logged_users[email]

    def get_logged_users(self):
        """Get all currently logged users."""
        return self.logged_users.copy()
