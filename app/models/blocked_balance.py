import uuid
from datetime import datetime, timedelta

from app.models.user_performance import update_user_performance
from .create_db import db

class BlockedBalanceDB(db.Model):
	__tablename__ = 'balances_bloqueados'

	id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	user_id = db.Column(db.String(36), nullable=False)
	amount_usdt = db.Column(db.Float, nullable=False)
	amount_crypto = db.Column(db.Float, nullable=False)
	currency = db.Column(db.String(255), nullable=False)
	exchange = db.Column(db.String(255), nullable=False, default="general")
	by_bot = db.Column(db.String(255), nullable=False)
	finished = db.Column(db.Boolean, nullable=False, default=False)
	start_with = db.Column(db.String(4), nullable=True)
	market_type = db.Column(db.String(4), nullable=True)
	fecha = db.Column(db.DateTime, default=datetime.utcnow)

	@property
	def serialize(self):
		return {
			c.name: getattr(self, c.name)
			for c in self.__table__.columns
		}

	def save(self):
		db.session.add(self)
		db.session.commit()

def add_quantity_to_block(
	user_id: str, 
	amount_usdt: float, 
	amount_crypto: float, 
	currency: str, 
	by_bot: str,
	order: str,
	exchange: str = "general",
	market_type: str = "swap"
) -> bool:
	"""
	Añade o actualiza un balance bloqueado
	"""
	from main import app_instance
	app = app_instance

	if app and hasattr(app, 'app_context'):
		with app.app_context():
			try:
				# Buscar registro existente
				existing_blocked = BlockedBalanceDB.query.filter_by(
					user_id=user_id,
					currency=currency,
					exchange=exchange,
					by_bot=by_bot,
					finished=False
				).first()

				if existing_blocked:
					# Actualizar montos existentes
					existing_blocked.amount_usdt += amount_usdt
					existing_blocked.amount_crypto += amount_crypto
					
					opposite_to_what_was_beginning = "sell" if order == "buy" else "buy"
					
					# if existing_blocked.amount_crypto <= 0:
					if opposite_to_what_was_beginning == existing_blocked.start_with:
						update_user_performance(user_id,  existing_blocked.amount_usdt)
						existing_blocked.finished = True
				else:
					# Crear nuevo registro
					new_blocked = BlockedBalanceDB(
						user_id=user_id,
						amount_usdt=amount_usdt,
						amount_crypto=amount_crypto,
						currency=currency,
						by_bot=by_bot,
						exchange=exchange,
						market_type=market_type,
						start_with=order
					)
					db.session.add(new_blocked)
				
				db.session.commit()
				return True
			except Exception as e:
				db.session.rollback()
				print(f"Error añadiendo cantidad bloqueada: {e}")
				return False
	return False

def get_blocked_quantity(user_id: str, currency: str, by_bot: str, exchange: str = "general", finished: bool = False) -> dict:
	"""
	Obtiene los montos bloqueados (USDT y crypto) para un usuario
	Devuelve un diccionario con ambos montos del registro más reciente
	"""
	from main import app_instance
	app = app_instance

	if app and hasattr(app, 'app_context'):
		with app.app_context():
			try:
				# Obtener el registro más reciente ordenando por fecha descendente
				blocked = BlockedBalanceDB.query.filter_by(
					user_id=user_id,
					currency=currency,
					by_bot=by_bot,
					exchange=exchange,
					finished=finished
				).order_by(BlockedBalanceDB.fecha.desc()).first()
				
				if blocked:
					return {
						'amount_usdt': blocked.amount_usdt,
						'amount_crypto': blocked.amount_crypto,
						'start_with': blocked.start_with,
					}
			except Exception as e:
				print(f"Error obteniendo cantidad bloqueada: {e}")
	return {'amount_usdt': 0.0, 'amount_crypto': 0.0, 'start_with': None}

def get_balance_blocked_total_usdt(user_id: str) -> float:
	from main import app_instance
	app = app_instance

	if app and hasattr(app, 'app_context'):
		with app.app_context():
			try:
				blocked_records = BlockedBalanceDB.query.filter_by(
					user_id=user_id,
					finished=False
				).all()
				
				total_amount = sum(record.amount_usdt for record in blocked_records)
				
				return float(total_amount)
			except Exception as e:
				print(f"Error obteniendo balance bloqueado total para {user_id}: {e}")
				return 0.0
	return 0.0

def get_all_balance_blocked(user_id: str, days: int):
	from main import app_instance
	app = app_instance

	if app and hasattr(app, 'app_context'):
		with app.app_context():
			try:
				start_date = datetime.now() - timedelta(days=days)

				blocked_records = BlockedBalanceDB.query.filter(
					BlockedBalanceDB.user_id == user_id,
					BlockedBalanceDB.fecha >= start_date,
					BlockedBalanceDB.fecha <= datetime.now() +  timedelta(days=1),
					BlockedBalanceDB.finished,
				).order_by(BlockedBalanceDB.fecha.asc()).all()
				
				return blocked_records
			except Exception as e:
				print(f"Error obteniendo la lista de balances de {user_id}: {e}")
				return []
	return []