#app/Aplicacion.py

#app/Aplicacion.py

from flask import Flask
from flask_cors import CORS
from flask_login import LoginManager  # Import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel, _  # Import Babel and _ function for translations

from app.models.create_db import db
from app.models.users import User  # Import the User model


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
        with self.app.app_context():
           db.create_all()

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
