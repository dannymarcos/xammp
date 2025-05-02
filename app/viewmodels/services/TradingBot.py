import ccxt
import pandas as pd
import os
import time
import logging
import traceback
from dotenv import load_dotenv
from threading import Lock, Thread
from typing import Dict, Optional, List, Literal
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import signal
import sys
from app.viewmodels.api.kraken.KrakenAPI import KrakenAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ----------------------------
# Configuration Models
# ----------------------------

class TradingConfig(BaseModel):
    """
    Validated trading configuration using Pydantic
    """
    trading_pair: str = Field("BTC/USD", description="Trading pair (e.g., BTC/USD)")
    timeframe: str = Field("1h", description="Chart timeframe (1m, 1h, 1d)")
    trade_amount: float = Field(0.01, gt=0, description="Base trade amount in quote currency")
    trading_mode: Literal['spot', 'futures'] = Field("spot", description="Trading account type")
    max_active_trades: int = Field(1, ge=1, description="Maximum concurrent positions")
    stop_loss_pct: float = Field(0.02, gt=0, lt=0.5, description="Stop loss percentage (0.02 = 2%)")
    take_profit_pct: float = Field(0.04, gt=0, lt=1, description="Take profit percentage")

    @field_validator('trading_pair')
    def validate_pair(cls, v):
        if '/' not in v:
            raise ValueError("Pair must contain '/' (e.g., BTC/USD)")
        return v.upper()

# ----------------------------
# Trading Bot Implementation
# ----------------------------

class KrakenTradingBot:
    """
    Thread-safe singleton trading bot with:
    - Pydantic validated configuration
    - Proper rate limiting
    - Risk management
    - Real order execution
    """
    
    _instances = {}
    _lock = Lock()
    
    def __new__(cls, user_id: str, *args, **kwargs):
        """Singleton pattern implementation"""
        with cls._lock:
            if user_id not in cls._instances:
                cls._instances[user_id] = super().__new__(cls)
            return cls._instances[user_id]
    
    def __init__(self, user_id, kraken_api: KrakenAPI, api_key: str, api_secret: str, config: Dict):
        if hasattr(self, '_initialized'):
            logger.debug(f"Bot instance for user {user_id} already initialized, skipping initialization")
            return
            
        logger.info(f"Initializing trading bot for user {user_id}")
        
        try:
            # Validate configuration
            logger.debug(f"Validating configuration for user {user_id}")
            self.config = TradingConfig(**config)
            self.user_id = user_id
            self.kraken_api = kraken_api
            
            logger.debug(f"Setting up exchange connection for user {user_id}")
            self.exchange = ccxt.kraken({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {
                    'adjustForTimeDifference': True
                }
            })
                    
            # Trading state
            self.running = False
            self.active_trades = []
            self.trade_history = []
            self._initialized = True
            self._last_update = datetime.now()

            logger.info(f"✅ Successfully initialized bot for user {user_id}")
            logger.debug(f"⚙️ Configuration for user {user_id}:\n{self.config.model_dump_json(indent=4)}")
        except Exception as e:
            logger.error(f"Failed to initialize bot for user {user_id}: {str(e)}")
            logger.debug(f"Initialization error details: {traceback.format_exc()}")
            raise
        
    def _force_stop(self):
        self.running = False
        print(f"🛑 Stopped bot for {self.user_id}")

    def start(self):
        """Start the trading bot in a background thread"""
        logger.info(f"Attempting to start bot for user {self.user_id}")
        
        if self.running:
            logger.warning(f"⚠️ Bot for user {self.user_id} is already running")
            return False

        try:
            self.running = True
            logger.info(f"Creating trading thread for user {self.user_id}")
            self.thread = Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            logger.info(f"✅ Successfully started bot for user {self.user_id}")
            return True
        except Exception as e:
            self.running = False
            logger.error(f"Failed to start bot for user {self.user_id}: {str(e)}")
            logger.debug(f"Start error details: {traceback.format_exc()}")
            return False

    def _run_loop(self):
        """Main trading loop"""
        logger.info(f"🚀 Starting trading loop for user {self.user_id}")
        loop_count = 0
        
        while self.running:
            loop_count += 1
            logger.debug(f"Trading loop iteration {loop_count} for user {self.user_id}")
            
            try:
                start_time = time.time()
                
                # 1. Fetch market data
                logger.debug(f"Fetching market data for {self.config.trading_pair}")
                ohlcv = self._fetch_market_data()
                if ohlcv is None:
                    logger.warning(f"No market data available for {self.config.trading_pair}, skipping iteration")
                    continue

                # 2. Generate trading signals
                logger.debug(f"Generating trading signals for {self.config.trading_pair}")
                signals = self._generate_signals(ohlcv)
                logger.info(f"Generated signals for {self.config.trading_pair}: {signals}")

                # 3. Execute trades
                logger.debug(f"Executing trading strategy based on signals")
                self._execute_strategy(signals)

                # 4. Manage risk
                logger.debug(f"Performing risk management checks")
                self._check_risk_management()

                # 5. Respect rate limits
                elapsed = time.time() - start_time
                sleep_time = max(
                    self.exchange.rateLimit / 1000 - elapsed,
                    1  # Minimum 1 second
                )
                logger.debug(f"Iteration took {elapsed:.2f}s, sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"⚠️ Trading loop error for user {self.user_id}: {str(e)}")
                logger.debug(f"Trading loop error details: {traceback.format_exc()}")
                logger.info(f"Pausing trading loop for 30 seconds after error")
                time.sleep(30)

    def _fetch_market_data(self) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data from Kraken"""
        try:
            logger.debug(f"Fetching OHLCV data for {self.config.trading_pair} with timeframe {self.config.timeframe}")
            ohlcv = self.exchange.fetch_ohlcv(
                symbol=self.config.trading_pair,
                timeframe=self.config.timeframe,
                limit=100
            )
            
            if not ohlcv or len(ohlcv) == 0:
                logger.warning(f"No OHLCV data returned for {self.config.trading_pair}")
                return None
                
            logger.debug(f"Received {len(ohlcv)} OHLCV candles for {self.config.trading_pair}")
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Log some statistics about the data
            latest_candle = df.iloc[-1]
            logger.debug(f"Latest candle for {self.config.trading_pair}: Open={latest_candle['open']}, Close={latest_candle['close']}, Volume={latest_candle['volume']}")
            
            return df
        except Exception as e:
            logger.error(f"❌ Failed to fetch market data for {self.config.trading_pair}: {str(e)}")
            logger.debug(f"Market data fetch error details: {traceback.format_exc()}")
            self._force_stop()
            return None

    def _generate_signals(self, df: pd.DataFrame) -> Dict:
        """Generate trading signals from market data"""
        signals = {'buy': False, 'sell': False}

        # Calculate indicators
        df['EMA12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['EMA26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['RSI'] = self._calculate_rsi(df['close'], 14)

        last = df.iloc[-1]
        prev = df.iloc[-2]

        # EMA Crossover Strategy
        if last['EMA12'] > last['EMA26'] and prev['EMA12'] <= prev['EMA26']:
            signals['buy'] = True
        elif last['EMA12'] < last['EMA26'] and prev['EMA12'] >= prev['EMA26']:
            signals['sell'] = True

        # RSI Strategy
        if last['RSI'] < 30:
            signals['buy'] = True
        elif last['RSI'] > 70:
            signals['sell'] = True

        signals["buy"] = True # TODO: Remove

        return signals

    def _execute_strategy(self, signals: Dict):
        """Execute trades based on signals"""
        # Check max active trades
        if len(self.active_trades) >= self.config.max_active_trades:
            return

        current_price = self._get_current_price()

        # Buy Signal
        if signals['buy'] and not self.active_trades:
            order = self._create_order('buy', current_price)
            if order:
                self.active_trades.append({
                    'id': order['id'],
                    'side': 'buy',
                    'price': float(order['price']),
                    'stop_loss': current_price * (1 - self.config.stop_loss_pct),
                    'take_profit': current_price * (1 + self.config.take_profit_pct),
                    'time': datetime.now()
                })

        # Sell Signal
        elif signals['sell'] and self.active_trades:
            for trade in self.active_trades[:]:  # Create copy for iteration
                if trade['side'] == 'buy':
                    order = self._create_order('sell', current_price)
                    if order:
                        self.active_trades.remove(trade)
                        self.trade_history.append({
                            **trade,
                            'exit_price': float(order['price']),
                            'exit_time': datetime.now(),
                            'pnl': (float(order['price']) - trade['price']) * self.config.trade_amount
                        })

    def _check_risk_management(self):
        """Check stop loss and take profit levels"""
        if not self.active_trades:
            return

        current_price = self._get_current_price()

        for trade in self.active_trades[:]:
            # Check stop loss
            if current_price <= trade['stop_loss']:
                print(f"⚠️ Stop loss triggered for trade {trade['id']}")
                order = self._create_order('sell', current_price)
                if order:
                    self.active_trades.remove(trade)
                    self._record_trade_result(trade, current_price, 'stop_loss')

            # Check take profit
            elif current_price >= trade['take_profit']:
                print(f"🎯 Take profit triggered for trade {trade['id']}")
                order = self._create_order('sell', current_price)
                if order:
                    self.active_trades.remove(trade)
                    self._record_trade_result(trade, current_price, 'take_profit')

    def _create_order(self, side: str, price: float) -> Optional[Dict]:
        """Create order with proper error handling"""
        try:
            order = self.exchange.create_order(
                symbol=self.config.trading_pair,
                type='market',
                side=side,
                amount=self.config.trade_amount,
                params={
                    'trading_engine': self.config.trading_mode,
                    'leverage': 2 if self.config.trading_mode == 'futures' else 1
                }
            )
            print(f"✅ {side.upper()} order executed: {order['id']}")

            self.kraken_api.add_order_to_db({"id": "pepe", "symbol": self.config.trading_pair})
            return order
        except Exception as e:
            print(f"❌ Failed to execute {side} order: {str(e)}")
            return None

    def _get_current_price(self) -> float:
        """Get current market price"""
        ticker = self.exchange.fetch_ticker(self.config.trading_pair)
        return float(ticker['last'])

    def _calculate_rsi(self, series: pd.Series, period: int) -> pd.Series:
        """Calculate Relative Strength Index"""
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _record_trade_result(self, trade: Dict, exit_price: float, reason: str):
        """Record completed trade"""
        self.trade_history.append({
            **trade,
            'exit_price': exit_price,
            'exit_time': datetime.now(),
            'pnl': (exit_price - trade['price']) * self.config.trade_amount,
            'exit_reason': reason
        })

    def stop(self):
        """Stop the trading bot"""
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join()
        print(f"🛑 Stopped bot for {self.user_id}")

    @classmethod
    def get_instance(cls, user_id: str) -> Optional['KrakenTradingBot']:
        """Get existing bot instance"""
        with cls._lock:
            return cls._instances.get(user_id)

    @classmethod
    def stop_instance(cls, user_id: str) -> bool:
        """Stop and remove bot instance"""
        with cls._lock:
            if user_id in cls._instances:
                bot = cls._instances[user_id]
                bot.stop()
                del cls._instances[user_id]
                return True
            return False

# ----------------------------
# Example Usage
# ----------------------------

def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize Kraken API
    kraken = ccxt.kraken({
        'apiKey': os.getenv("KRAKEN_API_KEY"),
        'secret': os.getenv("KRAKEN_API_SECRET"),
        'enableRateLimit': True,
        'options': {
            'adjustForTimeDifference': True
        }
    })
    
    # Validate configuration
    config = {
        "trading_pair": "ETfH/USD",
        "timeframe": "1h",
        "trade_amount": 0.01,
        "trading_mode": "spot",
        "max_active_trades": 1,
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.04
    }
    
    # Create and start bot
    bot = KrakenTradingBot(
        user_id="example_user_123",
        api_key=os.getenv("KRAKEN_API_KEY"),
        api_secret=os.getenv("KRAKEN_API_SECRET"),
        kraken_api=kraken,
        config=config
    )
    
    # Handle graceful shutdown
    def signal_handler(sig, frame):
        print("\nShutting down gracefully...")
        bot.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start trading
    bot.start()
    
    # Keep main thread alive
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
