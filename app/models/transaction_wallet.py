import uuid
from .create_db import db
from datetime import datetime

class FoundWallet(db.Model):
    __tablename__ = 'transaction_wallet'

    # UUID as primary key
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(36), nullable=False)
    ref = db.Column(db.String(255), nullable=False)
    time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship('User', backref='transaction_wallets')
    verification = db.Column(db.Boolean, nullable=False, default=False)
    red = db.Column(db.String(255), nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False)  # 'deposit' or 'withdrawal'

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

def create_found_wallet(user_id: str, amount: float, currency: str, ref: str, red: str, transaction_type: str):
    """
    Creates a new found wallet entry.
    """
    from main import app_instance
    app = app_instance

    if transaction_type not in ["deposit", "withdrawal"]:
        return None

    if app and hasattr(app, 'app_context'):
        with app.app_context():
            try:
                found_wallet = FoundWallet(
                    user_id=user_id,
                    amount=amount,
                    currency=currency,
                    ref=ref,
                    red=red,
                    transaction_type=transaction_type
                )
                db.session.add(found_wallet)
                db.session.commit()
                return found_wallet.serialize
            except Exception as e:
                db.session.rollback()
                print(f"Error creating found wallet: {e}")
                return None
    return None

def get_found_wallets_by_user(user_id: str):
    """
    Gets all found wallet entries for a specific user.
    """
    from main import app_instance
    app = app_instance

    if app and hasattr(app, 'app_context'):
        with app.app_context():
            try:
                found_wallets = FoundWallet.query.filter_by(user_id=user_id).order_by(FoundWallet.time.desc()).all()
                return [wallet.serialize for wallet in found_wallets]
            except Exception as e:
                print(f"Error getting found wallets for user {user_id}: {e}")
                return []
    return []

def get_found_wallet_by_id(wallet_id: str):
    """
    Gets a specific found wallet entry by ID.
    """
    from main import app_instance
    app = app_instance

    if app and hasattr(app, 'app_context'):
        with app.app_context():
            try:
                found_wallet = FoundWallet.query.get(wallet_id)
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
                found_wallet = FoundWallet.query.get(wallet_id)
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