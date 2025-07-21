#proyecto_aegisia_main/app/models/create_db.py

from flask_sqlalchemy import SQLAlchemy 

db = SQLAlchemy()

# Importa todos tus modelos aquí para que Flask-Migrate los detecte
from .users import User
from .trades import Trade
from .strategies import Strategy
from .transaction_wallet import FoundWallet
from .wallet import WalletBD
from .performance_aegis import PerformanceAegis
from .referral_earnings import ReferralEarnings