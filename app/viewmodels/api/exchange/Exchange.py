from app.viewmodels.api.exchange.FatherExchange import Exchange
from app.viewmodels.api.exchange.Kraken.KrakenExchange import KrakenExchange
from app.viewmodels.api.exchange.Kraken.KrakenAPIFutures import KrakenFuturesExchange
from app.viewmodels.api.exchange.Kraken.KrakenSpotExchange import KrakenSpotExchange
from app.viewmodels.api.exchange.Bingx.BingxExchange import BingxExchange

class ExchangeFactory:
    """
    Clase principal para poder acceder a cualquier exchange usando la mismas funciones
    (usando la arquitectura factory)
    """
    @staticmethod
    def create_exchange(name: str, user_id=None, trading_mode="spot") -> Exchange:
        if name.lower() == "kraken":
            return KrakenExchange(user_id=user_id)
        elif name.lower() == "kraken_future":
            return KrakenFuturesExchange(user_id=user_id)
        elif name.lower() == "kraken_spot":
            return KrakenSpotExchange(user_id=user_id)
        elif name.lower() == "bingx":
            return BingxExchange(user_id=user_id, trading_mode=trading_mode)
        else:
            raise ValueError(f"Exchange no soportado: {name}")