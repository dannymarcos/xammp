# app/config.py

class Config:
    SECRET_KEY = 'your_secret_key'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root@localhost/users'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TRADING_MODE='spot'
    SYMBOL = 'XBTUSD'


