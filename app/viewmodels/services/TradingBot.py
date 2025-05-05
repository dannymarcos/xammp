import logging
import os
import signal
import sys
import time
import traceback
from datetime import datetime
from threading import Lock, Thread
from typing import Dict, Literal, Optional

import ccxt
import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

from app.models.trades import get_open_trades_from_user
from app.models.users import add_last_error_message
from app.viewmodels.api.kraken.KrakenAPI import KrakenAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ----------------------------
# Q-Learning Table
# ----------------------------

class SimpleQTable:
    """Q-learning table for trading decisions with incremental updates"""
    
    def __init__(self, q_table_path='q_table.csv'):
        self.q_table_path = q_table_path
        self.new_entries = []
        try:
            self.q_table = pd.read_csv(q_table_path)
            logger.info(f"Loaded Q-table from {q_table_path}")
        except Exception as e:
            logger.warning(f"Could not load Q-table: {str(e)}")
            self.q_table = pd.DataFrame(columns=['state','buy','sell','hold'])
            
    def get_action(self, state: str) -> str:
        """Get best action for given state"""
        try:
            row = self.q_table[self.q_table['state'] == state].iloc[0]
            return max(['buy','sell','hold'], key=lambda x: row[x])
        except:
            # Track new states encountered
            if state not in [e['state'] for e in self.new_entries]:
                self.new_entries.append({
                    'state': state,
                    'buy': 0.5,  # Initial Q-values
                    'sell': 0.5,
                    'hold': 0.5
                })
            return 'hold'  # Default action if state not found
            
    def update_q_value(self, state: str, action: str, reward: float, learning_rate=0.1):
        """Update Q-value for state-action pair"""
        # First check new entries
        for entry in self.new_entries:
            if entry['state'] == state:
                entry[action] = (1 - learning_rate) * entry[action] + learning_rate * reward
                return
                
        # Then check existing table
        if state in self.q_table['state'].values:
            idx = self.q_table[self.q_table['state'] == state].index[0]
            self.q_table.at[idx, action] = (1 - learning_rate) * self.q_table.at[idx, action] + learning_rate * reward
            
    def save(self, path=None):
        """Save Q-table to file, merging new entries"""
        path = path or self.q_table_path
        # Merge new entries with existing table
        if self.new_entries:
            new_df = pd.DataFrame(self.new_entries)
            self.q_table = pd.concat([self.q_table, new_df]).drop_duplicates('state', keep='last')
            self.new_entries = []
        self.q_table.to_csv(path, index=False)

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
            self.bot_errors = []
            self.signals = []
            self.q_table = SimpleQTable()

            logger.info(f"✅ Successfully initialized bot for user {user_id} \n {self.config.model_dump_json(indent=4)}")
            logger.debug(f"⚙️ Configuration for user {user_id}:\n{self.config.model_dump_json(indent=4)}")
        except Exception as e:
            logger.error(f"Failed to initialize bot for user {user_id}: {str(e)}")
            logger.debug(f"Initialization error details: {traceback.format_exc()}")
            raise
        
    def _force_stop(self):
        self.running = False
        print(f"🛑 Stopped bot for {self.user_id}")

    def _add_bot_error(self, error):
        self.bot_errors.append(error)

    def _check_for_open_trades(self):
        return bool(self.active_trades)
        raise NotImplementedError("This has to add a logic to close opened orders to be able to work")
        
        open_trades_db = get_open_trades_from_user(self.user_id)

        if not open_trades_db or len(open_trades_db) == 0:
            logger.debug(f"No open trades found for {self.user_id} in Database")
            return []
        
        return open_trades_db

    def _should_stop(self):
        open_trades_found =  self._check_for_open_trades()

        limit_errors_passed = len(self.bot_errors) > 3

        # only stop bot if there are no open trades
        if not open_trades_found and limit_errors_passed:
            logger.warning(f"Stopping bot for user {self.user_id} due to many errors")
            logger.warning(f"Bot errors: \n {'\n - '.join(self.bot_errors)}")
            self._force_stop()
            add_last_error_message(self.user_id, '\n'.join(self.bot_errors))
            return True
    
    def start(self):
        """Start the trading bot in a background thread"""
        logger.info(f"Attempting to start bot for user {self.user_id}")
        
        if self.running:
            logger.warning(f"⚠️ Bot for user {self.user_id} is already running")
            return False

        try:
            self.running = True
            logger.debug(f"Creating trading thread for user {self.user_id}")
            self.thread = Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            logger.info(f"✅ Successfully started bot for user {self.user_id}")
            # Reset bot errors
            add_last_error_message(self.user_id, '')
            return True
        except Exception as e:
            self.running = False
            logger.error(f"Failed to start bot for user {self.user_id}: {str(e)}")
            logger.debug(f"Start error details: {traceback.format_exc()}")
            return False
        
    def _print_report(self):
        print(f"""
              📊📊 Report for user {self.user_id}

              Total trades: {len(self.trade_history)}
              Total wins: {len([trade for trade in self.trade_history if trade['profit'] > 0])}
              Total losses: {len([trade for trade in self.trade_history if trade['profit'] < 0])}

              Total profit: {sum([trade['profit'] for trade in self.trade_history])}
              Total ROI: {sum([trade['roi'] for trade in self.trade_history])}

              Total Signals: {len(self.signals)}
              Total Buys: {len([signal for signal in self.signals if signal['buy']])}
              Total Sells: {len([signal for signal in self.signals if signal['sell']])}
            """
            )

    def _run_loop(self):
        """Main trading loop"""
        logger.info(f"🚀 Starting trading loop for user {self.user_id}")
        loop_count = 0
        
        while self.running:
            loop_count += 1
            logger.debug(f"Trading loop iteration {loop_count} for user {self.user_id}")

            if self._should_stop():
                break
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
                logger.info(f"🧙 Generated signals for {self.config.trading_pair}: {signals}")

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
                
                # Periodically save Q-table every 100 iterations
                if loop_count % 100 == 0:
                    self.q_table.save()
                    
                time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"⚠️ Trading loop error for user {self.user_id}: {str(e)}")
                logger.info("Pausing trading loop for 30 seconds after error")
                traceback.print_exc()
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
        """Generate trading signals from market data using Q-learning and indicators"""
        signals = {'buy': False, 'sell': False}

        # Calculate indicators
        df['EMA12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['EMA26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['RSI'] = self._calculate_rsi(df['close'], 14)

        last = df.iloc[-1]
        prev = df.iloc[-2]

        # Create state representation
        ema_cross = 'up' if last['EMA12'] > last['EMA26'] else 'down'
        rsi_state = 'low' if last['RSI'] < 30 else 'high' if last['RSI'] > 70 else 'mid'
        state_key = f"ema_{ema_cross}_rsi_{rsi_state}"

        # Get Q-learning action
        q_action = self.q_table.get_action(state_key)

        # Combine with indicator strategies
        if q_action == 'buy' or \
           (last['EMA12'] > last['EMA26'] and prev['EMA12'] <= prev['EMA26']) or \
           (last['RSI'] < 30):
            signals['buy'] = True

        if q_action == 'sell' or \
           (last['EMA12'] < last['EMA26'] and prev['EMA12'] >= prev['EMA26']) or \
           (last['RSI'] > 70):
            signals['sell'] = True

        # for testing
        """ import random
        signals['buy'] = random.choice([True, False])
        signals['sell'] = random.choice([True, False]) """

        self.signals.append(signals) # Track signals
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
                # Get current market state
                ohlcv = self._fetch_market_data()
                if ohlcv is not None:
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['EMA12'] = df['close'].ewm(span=12, adjust=False).mean()
                    df['EMA26'] = df['close'].ewm(span=26, adjust=False).mean()
                    df['RSI'] = self._calculate_rsi(df['close'], 14)
                    last = df.iloc[-1]
                    ema_cross = 'up' if last['EMA12'] > last['EMA26'] else 'down'
                    rsi_state = 'low' if last['RSI'] < 30 else 'high' if last['RSI'] > 70 else 'mid'
                    entry_state = f"ema_{ema_cross}_rsi_{rsi_state}"
                else:
                    entry_state = "unknown"
                
                self.active_trades.append({
                    'id': order['id'],
                    'order_direction': 'buy',
                    'price': float(order['price']),
                    'stop_loss': current_price * (1 - self.config.stop_loss_pct),
                    'take_profit': current_price * (1 + self.config.take_profit_pct),
                    'time': datetime.now(),
                    'entry_state': entry_state
                })

   

        # Sell Signal
        elif signals['sell']: # #TODO: add system to track orders made and self.active_trades:
            for trade in self.active_trades[:]:  # Create copy for iteration
                if trade['order_direction'] == 'buy':
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
            logger.info(f"💵 Creating {side} order at {price} for {self.config.trading_pair} with {self.config.trade_amount} units")
            """ order = self.exchange.create_order(
                symbol=self.config.trading_pair,
                type='market', # TODO: Change to to accesos more types
                side=side,
                amount=self.config.trade_amount,
                params={
                    'trading_engine': self.config.trading_mode,
                    'leverage': 2 if self.config.trading_mode == 'futures' else 1
                }
            ) """

            order_created, _ = self.kraken_api.add_order("market", side, self.config.trade_amount, self.config.trading_pair, order_made_by="bot")
            
            if 'error' in order_created:
                raise Exception(order_created['error'])
            
            logger.info(f"✅ {side.upper()} order executed: {order_created['id']}")
            return order_created
        except Exception as e:
            logger.error(f"❌ Failed to create {side} order: {str(e)}")
            self._add_bot_error(f"❌ Failed to execute {side} order: {str(e)}")
            traceback.print_exc()
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
        """Record completed trade and update Q-values"""
        pnl = (exit_price - trade['price']) * self.config.trade_amount
        roi = (exit_price - trade['price']) / trade['price']
        
        # Calculate reward based on trade outcome
        reward = 0
        if reason == 'take_profit':
            reward = 1.0
        elif reason == 'stop_loss':
            reward = -1.0
        else:
            reward = 0.5 if pnl > 0 else -0.5
            
        # Get the state when trade was opened
        if hasattr(trade, 'entry_state'):
            self.q_table.update_q_value(trade['entry_state'], 
                                      trade['order_direction'], 
                                      reward)

        self.trade_history.append({
            **trade,
            'exit_price': exit_price,
            'exit_time': datetime.now(),
            'pnl': pnl,
            'roi': roi,
            'exit_reason': reason
        })

    def stop(self):
        """Stop the trading bot"""
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join()
        print(f"🛑 Stopped bot for {self.user_id}")
        self._print_report()
        self.q_table.save()  # Save Q-table on shutdown

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
