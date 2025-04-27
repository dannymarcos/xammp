# app/config.py

class Config:
    SECRET_KEY = 'your_secret_key'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:admin@localhost/botsito'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TRADING_MODE='spot'
    SYMBOL = 'XBTUSD'


