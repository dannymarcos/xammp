#app/Aplicacion.py

#app/Aplicacion.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_login import LoginManager  # Import LoginManager
from app.models.create_db import db
from app.models.users import User  # Import the User model

class Application:
   
    def __init__(self, config_object):
        self.app = Flask(__name__, template_folder="iu/templates", static_folder="iu/static")
        self.app.config.from_object(config_object)
        db.init_app(self.app) #Inicializamos db dentro del constructor
        CORS(self.app)

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
            # Since the user ID is the email in our case
            return User.query.get(str(user_id))

    def app_context(self): 
        return self.app.app_context()
