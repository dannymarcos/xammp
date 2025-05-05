import uuid
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
    timestamp = db.Column(db.DateTime, default=datetime.now)
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

        if app:
            with app.app_context():
                if by == "bot":
                    trades = Trade.query.filter_by(user_id=user_id, by="bot", status="open").order_by(Trade.timestamp.desc()).all()
                    return [trade.serialize for trade in trades]
                
                if by == "user":
                    trades = Trade.query.filter_by(user_id=user_id, by="user", status="open").order_by(Trade.timestamp.desc()).all()
                    return [trade.serialize for trade in trades]
                
                if by == "all":
                    trades = Trade.query.filter_by(user_id=user_id, status="open").order_by(Trade.timestamp.desc()).all()
                    return [trade.serialize for trade in trades]