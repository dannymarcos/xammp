import time
import traceback
from abc import ABC, abstractmethod
from flask import current_app
from app.models.create_db import db
from app.models.trades import Trade

class Exchange(ABC):
    def __init__(self, user_id=None, trading_mode=None):
        self.user_id = user_id
        self.trading_mode = trading_mode
    
    # Métodos comunes implementados
    
    def identification(self) -> str:
        pass
    
    def calculate_take_profit(self, current_price: float, take_profit_percent: float) -> float:
        return current_price * (1 + take_profit_percent)
    
    def get_nonce(self) -> int:
        return int(time.time() * 1000)
    
    def add_order_to_db(self, order):
        try:
            # Try to get the current app context
            try:
                app = current_app
                with app.app_context():
                    trade = Trade(**order)
                    db.session.add(trade)
                    db.session.commit()
                    print("✅ Order added to database")
                    return trade.serialize
            except RuntimeError:
                # If we're outside of application context, skip database save
                print("⚠️ Working outside of Flask application context, skipping database save")
                return {"status": "success", "message": "Order processed but not saved to database"}
        except Exception as e:
            traceback.print_exc()
            return {"error": str(e)}, 400

    # Métodos abstractos (interfaz común)
    @abstractmethod
    def get_creds_from_user(self):
        pass
    
    @abstractmethod
    def set_trading_mode(self, mode: str):
        pass
    
    @abstractmethod
    def add_order(self, symbol: str, order_type: str, side: str, amount: float, price: float, params=None):
        pass
    
    @abstractmethod
    def get_symbol_price(self, symbol: str) -> float:
        pass
    
    @abstractmethod
    def get_account_balance(self) -> dict:
        pass
    
    @abstractmethod
    def sign(self, data: bytes) -> str:
        pass
    
    # Métodos opcionales con implementación por defecto
    def calculate_stop_loss(self, target_price: float, stop_loss_percentage: float):
        raise NotImplementedError("Método no disponible para este exchange")
    
    def get_trades_history(self):
        raise NotImplementedError("Método no disponible para este exchange")
    
    def get_cryptos(self):
        raise NotImplementedError("Método no disponible para este exchange")
    
    def get_tickers_available_symbols(self):
        raise NotImplementedError("Método no disponible para este exchange")
    
    def fetch_ohlcv_optimized(self, symbol: str, timeframe: str = '1d', limit: int = 100):
        raise NotImplementedError("Método no disponible para este exchange")
    
    def get_market_context_for_llm(self):
        raise NotImplementedError("Método no disponible para este exchange")
    
    def get_signature(self, data: str) -> str:
        raise NotImplementedError("Método no disponible para este exchange")