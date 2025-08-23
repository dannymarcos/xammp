from .create_db import db
from datetime import datetime

class PerformanceUser(db.Model):
	__tablename__ = 'performance_user'

	id = db.Column(db.Integer, primary_key=True)
	user_id = db.Column(db.String(36), db.ForeignKey('users.id'))
	total_gains = db.Column(db.Float, nullable=False, default=0.0)
	total_losses = db.Column(db.Float, nullable=False, default=0.0)
	net_performance = db.Column(db.Float, nullable=False, default=0.0)
	date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
	
	def __repr__(self):
		return f'<PerformanceAegis(id={self.id}, amount={self.amount}, date={self.date})>'
	
	def serialize(self):
		return {
			'id': self.id,
			"total_gains": self.total_gains,
			"total_losses": self.total_losses,
			"net_performance": self.net_performance,
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

def get_user_balance(user_id):
	from main import app_instance
	app = app_instance

	if app and hasattr(app, 'app_context'):
		with app.app_context():
			try:
				record = PerformanceUser.query.filter_by(
					user_id=user_id,
				).first()

				return {
					"total_gains": record.total_gains,
					"total_losses": record.total_losses,
					"net_performance": record.net_performance
				}
			except Exception as e:
				print(f"Error obteniendo los datos del performance del usuario {user_id}: {e}")
				return {
					"total_gains": 0.00,
					"total_losses": 0.00,
					"net_performance": 0.00
				}

def update_user_performance(user_id, amount):
    from main import app_instance
    
    with app_instance.app_context():
        try:
            performance_record = PerformanceUser.query.filter_by(user_id=user_id).first()
            
            if performance_record:
                if amount >= 0:
                    performance_record.total_gains += amount
                else:
                    performance_record.total_losses += amount
                
                performance_record.net_performance += amount
                performance_record.update()
            else:
                total_losses = 0.0
                total_gains = 0.0

                if amount >= 0:
                    total_gains = amount
                else:
                    total_losses = amount
                
                new_record = PerformanceUser(
                    user_id=user_id,
                    total_gains=total_gains,
                    total_losses=total_losses,
                    net_performance=amount
                )
                new_record.save()
                
        except Exception as e:
            print(f"Error actualizando el performance del usuario {user_id}: {e}")
            db.session.rollback()