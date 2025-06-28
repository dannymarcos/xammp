from app.viewmodels.api.exchange.Exchange import ExchangeFactory

bingx = ExchangeFactory().create_exchange(name="bingx")
bingx.add_order("buy", "BTC/USDT:USDT", 0.0001)
