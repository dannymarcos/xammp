import uuid
from typing import Optional
from .create_db import db
from datetime import datetime
from .users import User

class Trade(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    order_id = db.Column(db.String(64))
    symbol = db.Column(db.String(16))
    order_direction = db.Column(db.String(8))  # 'buy' or 'sell'
    volume = db.Column(db.Float)
    price = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow())
    status = db.Column(db.String(16), default="open")
    by = db.Column(db.String(16)) # bot or user
    order_close_condition = db.Column(db.String(16), default="")
    order_description = db.Column(db.String(255))
    order_type = db.Column(db.String(16))
    stop_loss = db.Column(db.Float)
    take_profit = db.Column(db.Float)
    stop_loss_percent = db.Column(db.Float)
    take_profit_percent = db.Column(db.Float)
    comment = db.Column(db.String(255))
    actual_profit = db.Column(db.Float) # Profit in quote currency
    actual_profit_in_usd = db.Column(db.Float, nullable=True) # Profit in USD
    
    # Relationships
    user = db.relationship('User', backref='trades')

    @property
    def serialize(self):
        """Official SQLAlchemy-recommended serialization method"""
        return {
            c.name: getattr(self, c.name)
            for c in self.__table__.columns
        }

def get_all_trades_from_user(user_id, by="all"):
    # From the most recent
    if by == "bot":
        trades = Trade.query.filter_by(user_id=user_id, by="bot").order_by(Trade.timestamp.desc()).all()
        return [trade.serialize for trade in trades]
    if by == "user":
        trades = Trade.query.filter_by(user_id=user_id, by="user").order_by(Trade.timestamp.desc()).all()
        return [trade.serialize for trade in trades]
    
    trades = Trade.query.filter_by(user_id=user_id).order_by(Trade.timestamp.desc()).all()
    return [trade.serialize for trade in trades]

def get_open_trades_from_user(user_id, by="all"):
    from main import app_instance
    app = app_instance

    if app and hasattr(app, 'app_context'):
        with app.app_context():
            if by == "bot":
                trades = Trade.query.filter_by(user_id=user_id, by="bot", status="open").order_by(Trade.timestamp.desc()).all()
            elif by == "user":
                trades = Trade.query.filter_by(user_id=user_id, by="user", status="open").order_by(Trade.timestamp.desc()).all()
            elif by == "all":
                trades = Trade.query.filter_by(user_id=user_id, status="open").order_by(Trade.timestamp.desc()).all()
            else:
                return [] # Or raise an error for invalid 'by'
            return [trade.serialize for trade in trades]
    return [] # Return empty list if app_context is not available

def set_trade_actual_profit(trade_id: str, profit: float, app_context=None) -> bool:
    """
    Sets the actual_profit for a specific trade.
    """
    from main import app_instance
    app = app_context if app_context else app_instance

    if app and hasattr(app, 'app_context'):
        with app.app_context():
            try:
                trade = Trade.query.get(trade_id)
                if trade:
                    trade.actual_profit = profit
                    db.session.commit()
                    return True
                return False
            except Exception as e:
                db.session.rollback()
                # Consider logging the error e.g., app.logger.error(f"Error setting profit for trade {trade_id}: {e}")
                print(f"Error setting profit for trade {trade_id}: {e}") # Or use proper logging
                return False
    return False

def update_trade_status(trade_id: str, new_status: str, app_context=None) -> bool:
    """
    Updates the status for a specific trade.
    """
    from main import app_instance
    app = app_context if app_context else app_instance

    if app and hasattr(app, 'app_context'):
        with app.app_context():
            try:
                trade = Trade.query.get(trade_id)
                if trade:
                    trade.status = new_status
                    db.session.commit()
                    return True
                return False
            except Exception as e:
                db.session.rollback()
                # Consider logging the error
                print(f"Error updating status for trade {trade_id}: {e}") # Or use proper logging
                return False
    return False

def set_trade_actual_profit_in_usd(trade_id: str, profit_in_usd: Optional[float], app_context=None) -> bool:
    """
    Sets the actual_profit_in_usd for a specific trade.
    """
    from main import app_instance
    app = app_context if app_context else app_instance

    if app and hasattr(app, 'app_context'):
        with app.app_context():
            try:
                trade = Trade.query.get(trade_id)
                if trade:
                    trade.actual_profit_in_usd = profit_in_usd
                    db.session.commit()
                    return True
                return False
            except Exception as e:
                db.session.rollback()
                # Consider logging the error
                print(f"Error setting actual_profit_in_usd for trade {trade_id}: {e}") # Or use proper logging
                return False
    return False
