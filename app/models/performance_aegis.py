from .create_db import db
from datetime import datetime

class PerformanceAegis(db.Model):
    __tablename__ = 'performance_aegis'
    
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<PerformanceAegis(id={self.id}, amount={self.amount}, date={self.date})>'
    
    def serialize(self):
        return {
            'id': self.id,
            'amount': self.amount,
            'date': self.date.isoformat() if self.date else None
        }
    
    def save(self):
        db.session.add(self)
        db.session.commit()
    
    def update(self):
        db.session.commit()
    
    def delete(self):
        db.session.delete(self)
        db.session.commit() 

def get_balance_aegis():
    record = PerformanceAegis.query.get(1)
    if record:
        return record.amount
    return None
