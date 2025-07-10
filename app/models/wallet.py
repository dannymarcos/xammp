import uuid
from .create_db import db

class WalletBD(db.Model):
    __tablename__ = 'balance_wallet'

    # UUID as primary key
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(255), nullable=False)
    exchange = db.Column(db.String(255), nullable=False, default="general")  # Add exchange field

    @property
    def serialize(self):
        """Official SQLAlchemy-recommended serialization method"""
        return {
            c.name: getattr(self, c.name)
            for c in self.__table__.columns
        }
    
    def save(self):
        db.session.add(self)
        db.session.commit()

def add_found_wallet(user_id: str, amount: float, currency: str, exchange: str = "general"):
    """
    add a new found wallet entry.
    """
    from main import app_instance
    app = app_instance

    if app and hasattr(app, 'app_context'):
        with app.app_context():
            try:
                # Check if wallet already exists for this user, currency, and exchange
                existing_wallet = WalletBD.query.filter_by(
                    user_id=user_id, 
                    currency=currency, 
                    exchange=exchange
                ).first()
                
                if existing_wallet:
                    # Update existing wallet by adding the amount
                    existing_wallet.amount += amount
                    db.session.commit()
                    return existing_wallet.serialize
                else:
                    # Create new wallet entry
                    found_wallet = WalletBD(
                        user_id=user_id,
                        amount=amount,
                        currency=currency,
                        exchange=exchange
                    )
                    db.session.add(found_wallet)
                    db.session.commit()
                    return found_wallet.serialize
            except Exception as e:
                db.session.rollback()
                print(f"Error creating/updating found wallet: {e}")
                return None
    return None

def get_found_wallets_by_user(user_id: str, exchange: str = None):
    """
    Gets all found wallet entries for a specific user, optionally filtered by exchange.
    """
    from main import app_instance
    app = app_instance

    if app and hasattr(app, 'app_context'):
        with app.app_context():
            try:
                query = WalletBD.query.filter_by(user_id=user_id)
                if exchange:
                    query = query.filter_by(exchange=exchange)
                found_wallets = query.all()
                return [wallet.serialize for wallet in found_wallets]
            except Exception as e:
                print(f"Error getting found wallets for user {user_id}: {e}")
                return []
    return []

def get_balance_by_currency(user_id: str, currency: str, exchange: str = None):
    """
    Gets the balance for a specific currency for a specific user, optionally filtered by exchange.
    """
    from main import app_instance
    app = app_instance

    if app and hasattr(app, 'app_context'):
        with app.app_context():
            try:
                query = WalletBD.query.filter_by(user_id=user_id, currency=currency)
                if exchange:
                    query = query.filter_by(exchange=exchange)
                resultQuery = query.first()
                return resultQuery.amount if resultQuery else 0
            except Exception as e:
                print(f"Error getting balance for currency {currency}: {e}")
                return 0

def get_found_wallet_by_id(wallet_id: str):
    """
    Gets a specific found wallet entry by ID.
    """
    from main import app_instance
    app = app_instance

    if app and hasattr(app, 'app_context'):
        with app.app_context():
            try:
                found_wallet = WalletBD.query.get(wallet_id)
                return found_wallet.serialize if found_wallet else None
            except Exception as e:
                print(f"Error getting found wallet {wallet_id}: {e}")
                return None
    return None

def delete_found_wallet(wallet_id: str):
    """
    Deletes a found wallet entry by ID.
    """
    from main import app_instance
    app = app_instance

    if app and hasattr(app, 'app_context'):
        with app.app_context():
            try:
                found_wallet = WalletBD.query.get(wallet_id)
                if found_wallet:
                    db.session.delete(found_wallet)
                    db.session.commit()
                    return True
                return False
            except Exception as e:
                db.session.rollback()
                print(f"Error deleting found wallet {wallet_id}: {e}")
                return False
    return False 