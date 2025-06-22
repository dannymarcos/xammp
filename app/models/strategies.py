import uuid
from typing import Optional
from .create_db import db
from datetime import datetime
from .users import User

class Strategy(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    text = db.Column(db.Text)
    name = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    # Relationships
    user = db.relationship('User', backref='strategies')

    @property
    def serialize(self):
        """Official SQLAlchemy-recommended serialization method"""
        return {
            c.name: getattr(self, c.name)
            for c in self.__table__.columns
        }

def get_all_strategies_from_user(user_id: str) -> list[Strategy]:
    strategies =  Strategy.query.filter_by(user_id=user_id).all()
    return [item.serialize for item in strategies]

def get_strategy_by_id(user_id, strategy_id):
    from main import app_instance
    app = app_instance

    if app and hasattr(app, 'app_context'):
        with app.app_context():
            strategy =  Strategy.query.filter_by(id=strategy_id, user_id=user_id).first()
            return strategy
    return None # Return empty list if app_context is not available