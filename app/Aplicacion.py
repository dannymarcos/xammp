#app/Aplicacion.py

from flask import Flask, render_template
from flask_cors import CORS
from flask_login import LoginManager  # Import LoginManager
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
        self.app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000 # 1 year
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
        self.login_manager.login_view = 'auth.login'
        self._register_user_loader() # Register the user loader callback

        self.init_db()
        self._register_error_handlers()  # Register error handlers

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
                    
                    # Crear usuario admin si no existe
                    self._create_admin_user()
                    
                    # Inicializar tabla performance_aegis
                    self._init_performance_aegis()
        
        except sqlalchemy.exc.OperationalError as oe:
            error_msg = f"🚨 Error de conexión ({driver_name}): {str(oe)}"
            self.app.logger.critical(error_msg)
            self.app.logger.critical(f"URI de conexión: {self.app.config['SQLALCHEMY_DATABASE_URI']}")
            raise RuntimeError(error_msg) from oe
            
        except Exception as e:
            error_msg = f"🚨 Error crítico: {str(e)}"
            self.app.logger.exception(error_msg)
            raise RuntimeError(error_msg) from e

    def _create_admin_user(self):
        """Crea el usuario admin si no existe"""
        try:
            admin_email = self.app.config['ADMIN_EMAIL']
            admin_password = self.app.config['ADMIN_PASSWORD']
            admin_name = self.app.config['ADMIN_NAME']

            # Verificar si el usuario admin ya existe
            existing_admin = User.query.filter_by(email=admin_email).first()
            
            if existing_admin:
                self.app.logger.info(f"✅ Usuario admin ya existe: {admin_email}")
                return
            
            # Crear nuevo usuario admin
            admin_user = User(
                email=admin_email,
                full_name=admin_name,
                role="admin"
            )
            admin_user.set_password(admin_password)
            
            db.session.add(admin_user)
            db.session.commit()
            
            self.app.logger.info(f"✅ Usuario admin creado exitosamente: {admin_email}")
            
        except Exception as e:
            self.app.logger.error(f"❌ Error creando usuario admin: {str(e)}")
            db.session.rollback()

    def _init_performance_aegis(self):
        """Inicializa la tabla performance_aegis con un registro por defecto"""
        try:
            from app.models.performance_aegis import PerformanceAegis
            
            # Verificar si ya existe un registro
            existing_record = PerformanceAegis.query.first()
            
            if not existing_record:
                # Crear registro inicial con 0 amount
                performance = PerformanceAegis(amount=0.0)
                performance.save()
                self.app.logger.info("✅ Tabla performance_aegis inicializada con registro por defecto")
            else:
                self.app.logger.info("✅ Tabla performance_aegis ya tiene un registro")
                
        except Exception as e:
            self.app.logger.error(f"❌ Error inicializando tabla performance_aegis: {str(e)}")

    def register_blueprint(self, blueprint):
        self.app.register_blueprint(blueprint)

    def _register_error_handlers(self):
        """Register custom error handlers"""
        @self.app.errorhandler(404)
        def not_found_error(error):
            return render_template('errors/404.html'), 404

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
