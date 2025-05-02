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
    status = db.Column(db.String(16))
    by = db.Column(db.String(16)) # bot or user
    
    # Relationships
    user = db.relationship('User', backref='trades')

    @property
    def serialize(self):
        """Official SQLAlchemy-recommended serialization method"""
        return {
            c.name: getattr(self, c.name)
            for c in self.__table__.columns
        }

def get_all_trades_from_user(user_id):
    # From the most recent
    trades = Trade.query.filter_by(user_id=user_id).order_by(Trade.timestamp.desc()).all()
    return [trade.serialize for trade in trades]