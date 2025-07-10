import logging
import os
import signal
import sys
import time
import traceback
from datetime import datetime
from threading import Lock, Thread
from typing import Any, Dict, List, Literal, Optional, Tuple

import ccxt
import pandas as pd

# pandas_ta ya no se importa
# import pandas_ta as ta
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

from app.models.trades import (
    get_open_trades_from_user,
    set_trade_actual_profit,
    set_trade_actual_profit_in_usd,
    update_trade_status,
)
from app.models.users import add_last_error_message
from app.viewmodels.services.SimpleQTable import SimpleQTable
from app.viewmodels.api.exchange.Exchange import ExchangeFactory
from app.viewmodels.api.exchange.FatherExchange import Exchange
from app.lib.utils.trading_strategies import (
    calculate_indicators,
    strategy_rsi,
    strategy_basic_candlesticks,
    strategy_ema_crossover,
    strategy_manual_engulfing_threshold,
    strategy_q_learning,
)

logger = logging.getLogger(__name__)


# ----------------------------
# Configuration Models
# ----------------------------


class TradingConfig(BaseModel):
    """
    Validated trading configuration using Pydantic
    """

    trading_pair: str = Field("XBT/USD", description="Trading pair (e.g., BTC/USD)")
    timeframe: str = Field("5m", description="Chart timeframe (1m, 1h, 1d)")
    trade_amount: float = Field(
        0.0001, gt=0, description="Base trade amount in quote currency"
    )  # Assume base currency amount
    trading_mode: Literal["spot", "futures"] = Field(
        "spot", description="Trading account type"
    )
    max_active_trades: int = Field(1, ge=1, description="Maximum concurrent positions")
    stop_loss_pct: float = Field(
        0.02, gt=0, lt=0.5, description="Stop loss percentage (0.02 = 2%)"
    )
    take_profit_pct: float = Field(
        0.04, gt=0, lt=1, description="Take profit percentage"
    )
    strategy_id: str = Field(..., description="Trading strategy ID")

    @field_validator("trading_pair")
    def validate_pair(cls, v):
        """"
        Validate pair
        """

        if "/" not in v:
            raise ValueError("Pair must contain '/' (e.g., BTC/USD)")
        return v.upper()


# ----------------------------
# Trading Bot Implementation
# ----------------------------


class TradingBot:
    """
    Thread-safe singleton trading bot with:
    - Pydantic validated configuration
    - Proper rate limiting
    - Risk management
    - Real order execution (or mocked)
    - Integrated strategy functions
    """

    _instances = {}
    _lock = Lock()

    def __new__(cls, user_id: str, *args, **kwargs):
        """Singleton pattern implementation"""
        with cls._lock:
            if user_id not in cls._instances:
                cls._instances[user_id] = super().__new__(cls)
            return cls._instances[user_id]

    def __init__(
        self,
        user_id,
        exchange: Exchange,
        config: Dict,
        type_wallet: str
    ):
        if hasattr(self, "_initialized"):
            # logger.debug(f"Bot instance for user {user_id} already initialized, skipping initialization") # Can be noisy
            return

        logger.info("Initializing trading bot for user %s", user_id)

        try:
            # Validate configuration
            logger.debug("Validating configuration for user %s", user_id)
            self.config = TradingConfig(**config)
            self.user_id = user_id
            # Use the exchange factory to create an actual exchange instance
            self.exchange = exchange
            # self.exchange = exchange_factory.create_exchange(
            #     name=type_wallet, 
            #     user_id=user_id, 
            #     trading_mode=self.config.trading_mode
            # )

            logger.debug("Setting up exchange connection for user %s", user_id)

            # Trading state
            self.running = False
            self.active_trades: List[Dict[str, Any]] = (
                []
            )  # List of dicts for currently open trades managed by THIS bot instance
            self.trade_history: List[Dict[str, Any]] = (
                []
            )  # List of dicts for completed trades
            self._initialized = True
            self._last_update = datetime.now()
            self.bot_errors: List[str] = []  # List to store recent errors
            self.signals_history: List[Dict[str, Any]] = (
                []
            )  # List to track generated signals and their contributions
            self.q_table = SimpleQTable(
                q_table_path=f"q_tables/q_table_{user_id}.csv"
            )  # User-specific Q-table path

            logger.info("✅ Successfully initialized bot for user %s\n%s", user_id, self.config.model_dump_json(indent=4))
            logger.debug("⚙️ Configuration for user %s:\n%s", user_id, self.config.model_dump_json(indent=4))
        except Exception as e:
            logger.error("Failed to initialize bot for user %s: %s", user_id, str(e))
            logger.debug("Initialization error details: %s", traceback.format_exc())
            self._add_bot_error(f"Initialization failed: %s", e)
            raise  # Re-raise to indicate failure

    def _force_stop(self):
        self.running = False
        print("🛑 Forced stop for bot %s", self.user_id)

    def _add_bot_error(self, error):
        logger.error("Bot Error for %s: %s", self.user_id, error)
        self.bot_errors.append(error)
        # Keep a limited history of errors
        self.bot_errors = self.bot_errors[-10:]  # Keep last 10 errors

    def _check_for_open_trades_in_exchange(self):
        """Fetches open orders from the exchange (Kraken API)"""
        try:
            # This assumes your KrakenAPI class has a method to fetch open orders
            # If not, you'd use self.exchange.fetch_open_orders
            # For this example, we'll use the ccxt object
            # Note: Checking open *orders* is different from checking open *positions/trades*
            # Spot trading doesn't have "positions" in the same way futures does.
            # For spot, an "open trade" for your bot means a BUY order was filled
            # and you are now holding the asset, waiting to SELL.
            # We primarily manage this state in `self.active_trades`.
            # However, checking exchange open orders can catch orders placed but not yet filled.
            open_orders = self.exchange.fetch_open_orders(
                symbol=self.config.trading_pair
            )
            # logger.debug(f"Found {len(open_orders)} open orders on exchange for {self.user_id}") # Can be noisy
            # You might want to reconcile these with self.active_trades if needed
            return open_orders
        except Exception as e:
            logger.error(
                f"Failed to fetch open orders from exchange for {self.user_id}: {e}"
            )
            self._add_bot_error(f"Failed to fetch open orders: {e}")
            return []

    def _should_stop(self):
        # Check for open trades being managed by *this bot instance*
        # The original code also checked a DB function, keeping that structure
        open_trades_db = get_open_trades_from_user(self.user_id)
        # Consider bot's internal active trades as well
        has_active_trades = bool(self.active_trades) or bool(open_trades_db)

        # Check for excessive errors
        limit_errors_passed = (
            len(self.bot_errors) >= 1000
        )  # Stop if 1000 or more recent errors

        # Stop the bot if there are excessive errors AND no active trades/positions managed by the bot
        # If there are active trades, it might be better to try and manage them before stopping.
        if limit_errors_passed and not has_active_trades:
            logger.warning(
                f"Stopping bot for user {self.user_id} due to many errors ({len(self.bot_errors)})."
            )
            logger.warning(f"Bot errors: \n - " + "\n - ".join(self.bot_errors))
            self._force_stop()
            add_last_error_message(
                self.user_id, "\n".join(self.bot_errors)
            )  # Save errors to user model
            return True

        return False

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
            # Reset bot errors when starting
            self.bot_errors = []
            add_last_error_message(self.user_id, "")
            return True
        except Exception as e:
            self.running = False
            logger.error(f"Failed to start bot for user {self.user_id}: {str(e)}")
            logger.debug(f"Start error details: {traceback.format_exc()}")
            self._add_bot_error(f"Initialization failed: {e}")
            raise  # Re-raise to indicate failure

    def _print_report(self):
        print(
            f"""
              📊📊 Report for user {self.user_id}

              Total trades completed: {len(self.trade_history)}
              Total wins: {len([trade for trade in self.trade_history if trade.get('pnl', 0) > 0])}
              Total losses: {len([trade for trade in self.trade_history if trade.get('pnl', 0) < 0])}

              # Note: Summing PnL and ROI directly might be misleading across different trade amounts/pairs.
              # A more robust report would normalize these.
              Total PnL (sum): {sum([trade.get('pnl', 0) for trade in self.trade_history]):.6f}
              # Total ROI (sum): {sum([trade.get('roi', 0) for trade in self.trade_history]):.6f} # Summing ROI is generally not meaningful

              Total Signal Iterations: {len(self.signals_history)}
              Total Buy Signals Triggered: {len([s for s in self.signals_history if s.get('buy_triggered')])} # Count iterations where BUY was triggered
              Total Sell Signals Triggered: {len([s for s in self.signals_history if s.get('sell_triggered')])} # Count iterations where SELL was triggered

              Current Active Trades (managed by this instance): {len(self.active_trades)}
            """
        )

    def _run_loop(self):
        """Main trading loop"""
        logger.info("🚀 Starting trading loop for user %s", self.user_id)
        loop_count = 0
        # Consider managing an initial state or waiting period
        # time.sleep(5) # Optional initial delay

        while self.running:
            loop_count += 1
            # logger.debug(f"--- Trading loop iteration {loop_count} for user {self.user_id} ---") # Can be noisy

            if self._should_stop():
                logger.info("Bot _should_stop condition met for user %s. Exiting loop.", self.user_id)
                break  # Exit the loop if stop condition is met

            try:
                start_time = time.time()

                # 1. Fetch market data
                # logger.debug(f"Fetching market data for {self.config.trading_pair}") # Can be noisy
                ohlcv_df = self._fetch_market_data()
                if ohlcv_df is None or ohlcv_df.empty:
                    logger.warning(
                        f"No market data available or data insufficient for {self.config.trading_pair}, skipping iteration."
                    )
                    # Add a small delay before the next iteration if data fetch failed
                    time.sleep(5)
                    continue

                # Calculate indicators *once* for all strategies using manual implementations
                processed_df = calculate_indicators(ohlcv_df)
                # After dropping NA, check if there's still enough data (e.g., at least 2 rows for crossover/engulfing)
                if processed_df.empty or len(processed_df) < 2:
                    logger.warning(
                        "DataFrame empty or too short after indicator calculation, skipping iteration."
                    )
                    time.sleep(5)
                    continue

                # 2. Generate trading signals using the strategy functions
                # _generate_signals returns aggregated signals, Q-state, and contributing strategies
                aggregated_signals, q_state, contributing_strategies = (
                    self._generate_signals(processed_df)
                )

                # Log the aggregated signal and contributors
                buy_contrib = (
                    ", ".join(contributing_strategies["buy"])
                    if contributing_strategies["buy"]
                    else "None"
                )
                sell_contrib = (
                    ", ".join(contributing_strategies["sell"])
                    if contributing_strategies["sell"]
                    else "None"
                )
                logger.info(
                    f"🧙 Aggregated Signals: BUY={aggregated_signals['buy']} (Contrib: {buy_contrib}), SELL={aggregated_signals['sell']} (Contrib: {sell_contrib}) | Q-state: {q_state}"
                )

                # Track generated signals details for reporting
                self.signals_history.append(
                    {
                        "time": datetime.now(),
                        "buy_triggered": aggregated_signals["buy"],
                        "sell_triggered": aggregated_signals["sell"],
                        "buy_contributors": contributing_strategies["buy"],
                        "sell_contributors": contributing_strategies["sell"],
                        "q_state": q_state,
                    }
                )

                # 3. Execute trades based on aggregated signals
                # Pass the Q-state to execute strategy so it can be stored with the trade
                self._execute_strategy(aggregated_signals, q_state)

                # 4. Manage risk (check stop loss/take profit for active trades)
                self._check_risk_management()

                # 5. Respect rate limits and control loop speed
                elapsed = time.time() - start_time

                # Ensure we sleep for at least self.exchange.rateLimit / 1000 seconds
                # Add a minimum sleep time to avoid excessive polling and stay below timeframe frequency
                min_api_sleep = self.exchange.rateLimit / 1000
                # Calculate a reasonable sleep based on timeframe (e.g., run 4 times per timeframe duration)
                timeframe_seconds = self._timeframe_to_seconds(self.config.timeframe)
                ideal_loop_interval = max(
                    min_api_sleep * 2, timeframe_seconds / 4, 10
                )  # At least 2x API limit, 1/4 timeframe, min 10s

                sleep_time = max(
                    ideal_loop_interval - elapsed, 1
                )  # Ensure at least 1 second sleep

                # logger.debug(f"Iteration took {elapsed:.2f}s, sleeping for {sleep_time:.2f}s (Min API sleep: {min_api_sleep:.2f}s, Ideal interval: {ideal_loop_interval:.2f}s)") # Can be noisy

                # Periodically save Q-table
                if loop_count % 50 == 0:  # Save frequently enough
                    self.q_table.save()

                time.sleep(sleep_time)

            except ccxt.RateLimitExceeded as e:
                logger.warning(
                    f"Rate limit exceeded for user {self.user_id}. Waiting longer..."
                )
                self._add_bot_error(f"Rate limit exceeded: {e}")
                time.sleep(
                    self.exchange.rateLimit / 1000 * 3
                )  # Wait triple the rate limit time
            except (ccxt.ExchangeError, ccxt.NetworkError) as e:
                logger.error(
                    f"Exchange or Network error for user {self.user_id}: {type(e).__name__} - {e}"
                )
                self._add_bot_error(f"Exchange/Network error: {e}")
                time.sleep(60)  # Pause on exchange/network errors
            except Exception as e:
                logger.error(
                    f"⚠️ Unhandled trading loop error for user {self.user_id}: {str(e)}"
                )
                logger.info(
                    "Pausing trading loop for 60 seconds after unhandled error."
                )
                traceback.print_exc()
                self._add_bot_error(f"Unhandled loop error: {e}")
                time.sleep(60)  # Pause longer on unhandled errors

        logger.info(f"Trading loop stopped for user {self.user_id}.")

    def _timeframe_to_seconds(self, timeframe: str) -> int:
        """Converts timeframe string to seconds."""
        try:
            if timeframe.endswith("m"):
                return int(timeframe[:-1]) * 60
            elif timeframe.endswith("h"):
                return int(timeframe[:-1]) * 3600
            elif timeframe.endswith("d"):
                return int(timeframe[:-1]) * 86400
            elif timeframe.endswith("w"):
                return int(timeframe[:-1]) * 604800
            elif timeframe.endswith("M"):
                return int(timeframe[:-1]) * 2592000  # Approximate month
            else:
                logger.warning(
                    f"Unknown timeframe format: {timeframe}. Assuming 60 seconds."
                )
                return 60  # Default to 1 minute
        except ValueError:
            logger.error(
                f"Invalid timeframe value: {timeframe}. Cannot convert to seconds."
            )
            return 60  # Fallback

    def _fetch_market_data(self) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data from Kraken"""
        try:
            # logger.debug(f"Fetching OHLCV data for {self.config.trading_pair} with timeframe {self.config.timeframe}") # Can be noisy
            # Fetch enough data for indicators (e.g., 26 for EMA26/RSI + buffer + 1 for engulfing)
            # 100 candles should be sufficient for most common indicators
            ohlcv = self.exchange.fetch_ohlcv_optimized(self.config.trading_pair, self.config.timeframe)
            if not ohlcv or len(ohlcv) == 0:
                logger.warning(
                    f"No OHLCV data returned for {self.config.trading_pair}."
                )
                return None
            
            
            # ohlcv = self.exchange.fetch_ohlcv(
            #     symbol=self.config.trading_pair,
            #     timeframe=self.config.timeframe,
            #     limit=100,
            # )

            # if not ohlcv or len(ohlcv) == 0:
            #     logger.warning(
            #         f"No OHLCV data returned for {self.config.trading_pair}."
            #     )
            #     return None

            # logger.debug(f"Received {len(ohlcv)} OHLCV candles for {self.config.trading_pair}") # Can be noisy
            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            
            # Handle timestamp conversion more robustly
            try:
                # First try with milliseconds
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            except (ValueError, TypeError):
                try:
                    # If that fails, try without unit specification (assumes seconds)
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
                except (ValueError, TypeError):
                    # If both fail, try parsing as datetime string
                    df["timestamp"] = pd.to_datetime(df["timestamp"])

            # Log info about the latest candle
            if not df.empty:
                latest_candle = df.iloc[-1]
                # logger.debug(f"Latest candle: Time={latest_candle['timestamp']}, Close={latest_candle['close']:.6f}") # Can be noisy
            # else: logger.warning("Fetched OHLCV data resulted in an empty DataFrame.") # Handled above

            logger.info(
                f"👀 Successfully fetched OHLCV data for {self.config.trading_pair}."
            )
            return df
        except Exception as e:
            logger.error(
                f"❌ Failed to fetch market data for {self.config.trading_pair}: {str(e)}"
            )
            logger.debug(f"Market data fetch error details: {traceback.format_exc()}")
            self._add_bot_error(f"Failed to fetch OHLCV: {e}")
            return None

    def _generate_signals(
        self, df: pd.DataFrame
    ) -> Tuple[Dict[str, bool], str, Dict[str, List[str]]]:
        """
        Orchestrates signal generation by calling individual strategy functions
        and aggregating their results.
        Requires DataFrame with indicators already calculated.
        Returns aggregated signals, Q-learning state, and dictionary of contributing strategy names.
        """
        aggregated_signals = {"buy": False, "sell": False}
        contributing_strategies = {"buy": [], "sell": []}
        q_state = "state_indicators_missing"  # Default state

        # Check if df has required indicator columns before proceeding
        # Note: individual strategies should also check for the indicators they need
        # This check is mainly for a general warning if calculate_indicators failed significantly
        # required_indicators = ['EMA12', 'EMA26', 'RSI', 'bullish_engulfing', 'bearish_engulfing']
        # if not all(col in df.columns and not df[col].isna().all() for col in required_indicators):
        #      logger.warning("_generate_signals received DataFrame without valid required indicators after calculation.")

        # Get signals from each strategy and collect contributors
        # EMA Crossover Strategy
        ema_signals = strategy_ema_crossover(df)
        if ema_signals["buy"]:
            aggregated_signals["buy"] = True
            contributing_strategies["buy"].append("EMA_Crossover")
        if ema_signals["sell"]:
            aggregated_signals["sell"] = True
            contributing_strategies["sell"].append("EMA_Crossover")

        # RSI Strategy
        rsi_signals = strategy_rsi(df)
        if rsi_signals["buy"]:
            aggregated_signals["buy"] = True
            contributing_strategies["buy"].append("RSI")
        if rsi_signals["sell"]:
            aggregated_signals["sell"] = True
            contributing_strategies["sell"].append("RSI")

        # Q-learning Strategy (returns signals and state)
        q_signals, current_q_state = strategy_q_learning(df, self.q_table)
        q_state = current_q_state  # Update q_state from the function call
        if q_signals["buy"]:
            aggregated_signals["buy"] = True
            contributing_strategies["buy"].append("Q_Learning")
        if q_signals["sell"]:
            aggregated_signals["sell"] = True
            contributing_strategies["sell"].append("Q_Learning")

        # Manual Engulfing + Threshold Strategy
        engulf_signals = strategy_manual_engulfing_threshold(df)
        if engulf_signals["buy"]:
            aggregated_signals["buy"] = True
            contributing_strategies["buy"].append("Manual_Engulfing_Threshold")
        if engulf_signals["sell"]:
            aggregated_signals["sell"] = True
            contributing_strategies["sell"].append("Manual_Engulfing_Threshold")

        # Basic Candlestick Strategy (Martillo, Estrella Fugaz)
        basic_candle_signals = strategy_basic_candlesticks(df)
        if basic_candle_signals["buy"]:
            aggregated_signals["buy"] = True
            contributing_strategies["buy"].append("Basic_Candlesticks")
        if basic_candle_signals["sell"]:
            aggregated_signals["sell"] = True
            contributing_strategies["sell"].append("Basic_Candlesticks")

        # Aggregate signals using simple OR logic across all strategies.
        # Note: The 'buy' or 'sell' flags from each strategy function are already True/False.
        # The logic here is just combining the contribution lists and the final boolean result.
        final_aggregated_signals = {
            "buy": aggregated_signals["buy"],
            "sell": aggregated_signals["sell"],
        }

        # Prevent simultaneous buy and sell signals if that's not desired
        # This prevents conflicting actions but means one signal gets ignored.
        # The strategy logic itself should ideally avoid this, but this is a safety check.
        if final_aggregated_signals["buy"] and final_aggregated_signals["sell"]:
            logger.warning(
                "Received simultaneous BUY and SELL signals. Resolving conflict."
            )
            # Simple conflict resolution: if no active trades, prioritize buy. If active trades, prioritize sell to exit.
            if not self.active_trades:
                logger.warning("Prioritizing BUY signal as no active trades.")
                final_aggregated_signals["sell"] = False
                contributing_strategies["sell"] = (
                    []
                )  # Clear conflicting signal contributors
            else:
                logger.warning("Prioritizing SELL signal to close active trades.")
                final_aggregated_signals["buy"] = False
                contributing_strategies["buy"] = (
                    []
                )  # Clear conflicting signal contributors

        # Also prevent buying if max trades are open, logs this in execute_strategy, no need to change signal here.
        # The check `len(self.active_trades) >= self.config.max_active_trades` is done in _execute_strategy

        return final_aggregated_signals, q_state, contributing_strategies

    def _execute_strategy(self, signals: Dict[str, bool], q_state: str):
        """
        Executes trading actions based on the aggregated signals.
        Simplified to act directly on buy/sell flags.
        """
        current_price = self._get_current_price()
        if current_price is None or current_price <= 0:
            logger.error("Could not get current price for execution logic.")
            return  # Cannot execute without price

        # --- Buy Logic ---
        # Only attempt to buy if a buy signal is true AND we are allowed to open a new trade
        if signals["buy"]:
            if len(self.active_trades) >= self.config.max_active_trades:
                logger.info(
                    f"Skipping BUY signal: Max active trades ({self.config.max_active_trades}) reached. Current: {len(self.active_trades)}"
                )
            else:
                logger.info(f"➡️ BUY signal received. Attempting to create BUY order.")
                # In a real bot, you'd use a Limit or Market order based on strategy
                # Using 'market' as per original code, price param is indicative but not used by exchange for market orders
                order_result = self._create_order(
                    "buy", current_price
                )  # order_result is the serialized DB Trade record
                if (
                    order_result
                    and order_result.get("id")
                    and order_result.get("order_id")
                ):  # Check for DB PK and Exchange ID
                    db_trade_id = order_result["id"]  # Database Primary Key
                    exchange_order_id = order_result[
                        "order_id"
                    ]  # Exchange's Transaction ID

                    actual_fill_price = order_result.get(
                        "price", current_price
                    )  # Price from DB record
                    trade_amount = order_result.get(
                        "volume", self.config.trade_amount
                    )  # Volume from DB record

                    # Parse timestamp if it's a string
                    entry_time_str = order_result.get("timestamp")
                    entry_time_dt = datetime.now()  # Fallback
                    if isinstance(entry_time_str, str):
                        try:
                            # Attempt to parse ISO format, common for DBs
                            entry_time_dt = datetime.fromisoformat(
                                entry_time_str.replace("Z", "+00:00")
                            )
                        except ValueError:
                            try:
                                # Fallback for other common formats if needed, or log warning
                                entry_time_dt = datetime.strptime(
                                    entry_time_str, "%Y-%m-%d %H:%M:%S.%f"
                                )
                            except ValueError:
                                logger.warning(
                                    f"Could not parse timestamp string: {entry_time_str}. Using current time."
                                )
                    elif isinstance(entry_time_str, datetime):
                        entry_time_dt = entry_time_str

                    # Store details of the new active trade
                    trade_details: Dict[str, Any] = {
                        "id": exchange_order_id,  # Exchange's transaction ID for logging/display
                        "db_trade_id": db_trade_id,  # Our database's primary key for this BUY trade
                        "order_direction": "buy",
                        "symbol": order_result.get("symbol", self.config.trading_pair),
                        "entry_price": actual_fill_price,
                        "entry_time": entry_time_dt,
                        "stop_loss": order_result.get(
                            "stop_loss",
                            actual_fill_price * (1 - self.config.stop_loss_pct),
                        ),  # Use DB SL or calculate
                        "take_profit": order_result.get(
                            "take_profit",
                            actual_fill_price * (1 + self.config.take_profit_pct),
                        ),  # Use DB TP or calculate
                        "entry_state": q_state,
                        "amount": trade_amount,
                    }
                    self.active_trades.append(trade_details)
                    print(
                        f"🎉 TRADE OPENED: BUY {trade_amount:.6f} {self.config.trading_pair} at {actual_fill_price:.6f} (Exchange ID: {exchange_order_id}, DB ID: {db_trade_id})"
                    )
                    logger.info(
                        f"✅ BUY order placed and tracked: Exchange ID {exchange_order_id}, DB ID {db_trade_id}. Entry Price: {actual_fill_price:.6f}, Amount: {trade_amount}"
                    )

                else:
                    logger.warning(
                        f"❌ Failed to create BUY order or order_result malformed: {order_result}"
                    )
                    # An error message would have been added in _create_order

        # --- Sell Logic ---
        # Only attempt to sell if a sell signal is true AND there are active trades to close
        # This logic closes ALL active BUY trades on a SELL signal. Adjust if you want to close only one.
        # Also, Stop Loss and Take Profit checks trigger sells.
        if signals["sell"] and self.active_trades:
            logger.info(
                f"⬅️ SELL signal received. Attempting to close active BUY trades."
            )

            # Iterate through a copy of the active trades list to avoid issues while removing items
            # Only consider trades opened as 'buy' for closing with a sell signal
            trades_to_close = [
                trade
                for trade in self.active_trades
                if trade["order_direction"] == "buy"
            ]

            if not trades_to_close:
                logger.debug("SELL signal received, but no active BUY trades to close.")
                return  # Nothing to sell if no buy trades open

            for trade in trades_to_close:
                trade_id = trade.get("id", "N/A")
                logger.info(
                    f"Attempting to close trade {trade_id} (BUY) with SELL order."
                )
                # Use the amount from the active trade details
                amount_to_sell = trade.get("amount", self.config.trade_amount)

                # Use current_price as the target price for the sell order
                order_result = self._create_order(
                    "sell", current_price
                )  # This is the serialized SELL DB record

                if (
                    order_result
                    and order_result.get("id")
                    and order_result.get("order_id")
                ):
                    sell_db_id = order_result["id"]  # DB PK of the SELL order
                    sell_exchange_id = order_result[
                        "order_id"
                    ]  # Exchange ID of the SELL order

                    actual_exit_price = order_result.get(
                        "price", current_price
                    )  # Actual fill price of the SELL

                    logger.info(
                        f"✅ SELL order (DB ID: {sell_db_id}, Exch ID: {sell_exchange_id}) placed to close BUY trade (Exch ID: {trade_id})"
                    )

                    # Record the trade result, passing the original BUY trade details and the DB ID of the new SELL trade
                    self._record_trade_result(
                        buy_trade_details=trade,
                        exit_price=actual_exit_price,
                        reason="sell_signal",
                        sell_order_db_id=sell_db_id,
                    )

                    # Remove the trade from the live active trades list
                    try:
                        self.active_trades.remove(trade)
                    except ValueError:
                        logger.warning(
                            f"Trade {trade_id} not found in active trades list during removal after SELL signal."
                        )

                else:
                    logger.warning(
                        f"❌ Failed to create SELL order to close trade {trade_id}."
                    )
                    # Error added in _create_order
                    # Decide how to handle failure to close a trade here.

    def _check_risk_management(self):
        """
        Checks stop loss and take profit levels for active trades.
        Closes trades if levels are hit.
        """
        if not self.active_trades:
            return  # Nothing to check if no active trades

        current_price = self._get_current_price()
        if current_price is None or current_price <= 0:
            logger.error("Could not get current price for risk management checks.")
            return  # Cannot check without price

        # logger.debug(f"Checking risk management for {len(self.active_trades)} active trades at price {current_price:.6f}") # Can be noisy

        # Iterate through a copy as we might remove items
        trades_to_check = self.active_trades[:]
        for trade in trades_to_check:
            # Only check SL/TP for open BUY trades
            if trade["order_direction"] == "buy":
                trade_id = trade.get("id", "N/A")
                entry_price = trade.get("entry_price", 0)  # Use .get for safety
                stop_loss = trade.get("stop_loss", 0)
                take_profit = trade.get("take_profit", 0)
                amount_to_sell = trade.get(
                    "amount", self.config.trade_amount
                )  # Use amount from trade

                # Check stop loss
                # Use a small tolerance (e.g., 1e-9) when comparing floats if exact comparison is risky,
                # but direct comparison is usually fine for these use cases.
                if (
                    stop_loss > 0 and current_price <= stop_loss
                ):  # Ensure SL is set (>0) and price dropped
                    print(
                        f"⚠️ STOP LOSS TRIGGERED for trade {trade_id} at {current_price:.6f} (SL: {stop_loss:.6f})"
                    )
                    logger.warning(f"Stop loss triggered for trade {trade_id}")

                    order_result = self._create_order(
                        "sell", current_price
                    )  # This is the serialized SELL DB record

                    if (
                        order_result
                        and order_result.get("id")
                        and order_result.get("order_id")
                    ):
                        sell_db_id = order_result["id"]  # DB PK of the SELL order
                        sell_exchange_id = order_result[
                            "order_id"
                        ]  # Exchange ID of the SELL order
                        actual_exit_price = order_result.get(
                            "price", current_price
                        )  # Actual fill price of the SELL

                        logger.info(
                            f"✅ SELL order (DB ID: {sell_db_id}, Exch ID: {sell_exchange_id}) placed for SL on BUY trade (Exch ID: {trade_id})"
                        )
                        self._record_trade_result(
                            buy_trade_details=trade,
                            exit_price=actual_exit_price,
                            reason="stop_loss",
                            sell_order_db_id=sell_db_id,
                        )

                        # Remove the trade from the live active trades list
                        try:
                            self.active_trades.remove(trade)
                        except ValueError:
                            logger.warning(
                                f"Trade {trade_id} not found in active trades list during removal after SL."
                            )
                    else:
                        logger.error(
                            f"❌ Failed to place SELL order for SL on trade {trade_id}"
                        )
                        self._add_bot_error(f"Failed SL order: {trade_id}")

                # Check take profit
                # Use a small tolerance (e.g., 1e-9) when comparing floats
                elif (
                    take_profit > 0 and current_price >= take_profit
                ):  # Ensure TP is set (>0) and price rose
                    print(
                        f"🎯 TAKE PROFIT TRIGGERED for trade {trade_id} at {current_price:.6f} (TP: {take_profit:.6f})"
                    )
                    logger.info(f"Take profit triggered for trade {trade_id}")

                    order_result = self._create_order(
                        "sell", current_price
                    )  # This is the serialized SELL DB record

                    if (
                        order_result
                        and order_result.get("id")
                        and order_result.get("order_id")
                    ):
                        sell_db_id = order_result["id"]  # DB PK of the SELL order
                        sell_exchange_id = order_result[
                            "order_id"
                        ]  # Exchange ID of the SELL order
                        actual_exit_price = order_result.get(
                            "price", current_price
                        )  # Actual fill price of the SELL

                        logger.info(
                            f"✅ SELL order (DB ID: {sell_db_id}, Exch ID: {sell_exchange_id}) placed for TP on BUY trade (Exch ID: {trade_id})"
                        )
                        self._record_trade_result(
                            buy_trade_details=trade,
                            exit_price=actual_exit_price,
                            reason="take_profit",
                            sell_order_db_id=sell_db_id,
                        )

                        # Remove the trade from the live active trades list
                        try:
                            self.active_trades.remove(trade)
                        except ValueError:
                            logger.warning(
                                f"Trade {trade_id} not found in active trades list during removal after TP."
                            )
                    else:
                        logger.error(
                            f"❌ Failed to place SELL order for TP on trade {trade_id}"
                        )
                        self._add_bot_error(f"Failed TP order: {trade_id}")

    def _create_order(self, side: str, price: float) -> Optional[Dict]:
        """
        Creates a MARKET order using the KrakenAPI instance.
        Logs errors and adds them to bot errors list.
        Returns the order response dictionary on success, None on failure.
        Assumes KrakenAPI add_order handles amount in base currency.
        """
        try:
            # Ensure amount is positive and reasonable (e.g., not zero)
            amount_to_trade = self.config.trade_amount
            if amount_to_trade <= 0:
                logger.error(
                    f"Trade amount is zero or negative ({amount_to_trade}). Cannot create order."
                )
                self._add_bot_error(f"Invalid trade amount: {amount_to_trade}")
                return None

            logger.info(
                f"💵 Attempting to create MARKET {side.upper()} order for {amount_to_trade} {self.config.trading_pair}"
            )

            # The price parameter here is not used by Kraken for MARKET orders,
            # but is kept in the signature as it was in the original code.
            # The actual fill price will be in the response or fetched later.

            ### CHANGE KRAKEN_API AND BINGXEXCHANGE
            volume = 0.0001 if self.config.trade_amount < 0.001 else self.config.trade_amount
            
            order_result = self.exchange.add_order(side,self.config.trading_pair,volume)

            # Handle tuple response (order_data, status_code)
            if isinstance(order_result, tuple):
                order_data, status_code = order_result
            else:
                order_data = order_result
                status_code = 200

            # order_data, _ = self.exchange.add_order(
            #     order_type="market",  # Using market orders as per original code logic
            #     order_direction=side,
            #     volume=amount_to_trade,  # Amount to trade (base currency)
            #     symbol=self.config.trading_pair,
            #     order_made_by="bot",
            # )

            if not order_data:
                error = order_data["error"]
                # kraken_api is expected to return (None, error_string) or (error_dict, None)
                # Handle different potential error formats from kraken_api
                error_message = (
                    str(error)
                    if isinstance(error, Exception)
                    else str(error) if error else "Unknown API error"
                )
                logger.error(f"KrakenAPI Error creating {side} order: {error_message}")
                self._add_bot_error(f"API Order Failed ({side}): {error_message}")
                return None

            # Check the structure of kraken_api's success response
            # Assuming it returns a dictionary including 'id' and potentially 'price' (fill price)
            if order_data and isinstance(order_data, dict) and "id" in order_data:
                logger.info(
                    f"✅ {side.upper()} order placed successfully: {order_data['id']}"
                )
                # Return the order_data received from the API, which should include the fill price for market orders
                return order_data
            else:
                logger.error(
                    f"API returned unexpected success response structure for {side} order: {order_data}"
                )
                self._add_bot_error(
                    f"API Order Succeeded but response bad ({side}): {order_data}"
                )
                return None  # Indicate failure due to bad response structure

        except Exception as e:
            logger.error(f"❌ Exception creating {side} order: {str(e)}")
            traceback.print_exc()
            self._add_bot_error(f"Exception creating {side} order: {e}")
            return None

    def _get_current_price(self) -> Optional[float]:
        """Get current market price using ccxt ticker."""
        try:
            # Fetching the ticker gives the last traded price quickly
            ticker = self.exchange.fetch_ticker(self.config.trading_pair)
            price = float(ticker.get("last"))  # Use .get for safety
            if price is None or price <= 0:
                logger.warning(
                    f"Fetched invalid price for {self.config.trading_pair}: {price}"
                )
                return None
            # logger.debug(f"Fetched current price for {self.config.trading_pair}: {price:.6f}") # Can be noisy
            return price
        except Exception as e:
            # logger.error(f"❌ Failed to get current price for {self.config.trading_pair}: {str(e)}") # Can be noisy if frequent
            self._add_bot_error(f"Failed to get price: {e}")
            return None

    def _record_trade_result(
        self,
        buy_trade_details: Dict[str, Any],
        exit_price: float,
        reason: str,
        sell_order_db_id: str,
    ):
        """
        Records a completed trade, calculates PnL/ROI, updates Q-values, and prints/logs result.
        Updates actual_profit for the sell trade and status for the buy trade in the database.
        Assumes 'buy' trades being closed by a 'sell'.
        """
        # buy_trade_details contains the info of the original BUY trade from self.active_trades
        # sell_order_db_id is the database PK of the SELL trade that closed this position

        original_buy_exchange_id = buy_trade_details.get(
            "id", "N/A"
        )  # Exchange ID of the original buy
        original_buy_db_trade_id = buy_trade_details.get(
            "db_trade_id", "N/A"
        )  # DB ID of the original buy

        logger.info(
            f"Recording trade result for original BUY trade (Exchange ID: {original_buy_exchange_id}, DB ID: {original_buy_db_trade_id}), closed by SELL trade (DB ID: {sell_order_db_id})"
        )

        # Ensure required fields are present
        entry_price = buy_trade_details.get("entry_price", 0)
        entry_action = buy_trade_details.get(
            "order_direction", "buy"
        )  # Should always be 'buy' here
        entry_state = buy_trade_details.get("entry_state", "unknown")
        trade_amount = buy_trade_details.get("amount", self.config.trade_amount)

        if entry_price == 0 or trade_amount == 0:
            logger.error(
                f"Cannot calculate PnL for trade {original_buy_exchange_id}: entry_price or trade_amount is zero."
            )
            # Potentially skip DB updates if PnL cannot be calculated, or record 0
            pnl = 0
            roi = 0
        else:
            pnl = (exit_price - entry_price) * trade_amount
            roi = (
                (exit_price - entry_price) / entry_price * 100
                if entry_price != 0
                else 0
            )

        outcome = "PROFIT" if pnl > 1e-9 else ("LOSS" if pnl < -1e-9 else "BREAKEVEN")

        # --- Database Updates ---
        pnl_in_usd: Optional[float] = None
        usd_equivalent_currencies = ["USD", "USDT", "USDC"]

        try:
            pair_details = self.config.trading_pair.split("/")
            if len(pair_details) == 2:
                quote_currency = pair_details[1].upper()
                if quote_currency in usd_equivalent_currencies:
                    pnl_in_usd = pnl
                else:
                    # Attempt to convert to USD
                    conversion_pair = f"{quote_currency}/USD"  # Assumes USD is the target for conversion
                    # Ensure the conversion pair is valid and different from the trading pair if quote is already USD-like
                    if (
                        quote_currency not in usd_equivalent_currencies
                    ):  # Redundant check, but safe
                        try:
                            ticker = self.exchange.fetch_ticker(conversion_pair)
                            conversion_rate = ticker.get("last")
                            if conversion_rate is not None and conversion_rate > 0:
                                pnl_in_usd = pnl * conversion_rate
                                logger.info(
                                    f"Converted PnL from {quote_currency} to USD: {pnl:.8f} {quote_currency} * {conversion_rate:.6f} = {pnl_in_usd:.2f} USD"
                                )
                            else:
                                logger.warning(
                                    f"Could not get valid conversion rate for {conversion_pair}. Last price: {conversion_rate}. Storing PnL in USD as None."
                                )
                                pnl_in_usd = None
                        except ccxt.BadSymbol:
                            logger.error(
                                f"Bad symbol for USD conversion: {conversion_pair}. Cannot convert PnL to USD. Storing PnL in USD as None."
                            )
                            pnl_in_usd = None
                        except Exception as e:
                            logger.error(
                                f"Error fetching ticker for USD conversion ({conversion_pair}): {e}. Storing PnL in USD as None."
                            )
                            pnl_in_usd = None
                    else:  # Should not happen if logic is correct, but handles case where quote_currency was USD-like
                        pnl_in_usd = pnl

            else:  # Should not happen if trading_pair is validated
                logger.warning(
                    f"Could not determine quote currency from trading pair: {self.config.trading_pair}. Storing PnL in USD as None."
                )
                pnl_in_usd = None

        except Exception as e:
            logger.error(
                f"Error during PnL to USD conversion logic: {e}. Storing PnL in USD as None."
            )
            pnl_in_usd = None

        if sell_order_db_id and sell_order_db_id != "N/A":
            # Store PnL in quote currency
            profit_set_quote = set_trade_actual_profit(
                trade_id=sell_order_db_id, profit=pnl
            )
            if profit_set_quote:
                logger.info(
                    f"Successfully set actual_profit (quote currency)={pnl:.8f} for SELL trade DB ID {sell_order_db_id}"
                )
            else:
                logger.error(
                    f"Failed to set actual_profit (quote currency) for SELL trade DB ID {sell_order_db_id}"
                )

            # Store PnL in USD
            profit_set_usd = set_trade_actual_profit_in_usd(
                trade_id=sell_order_db_id, profit_in_usd=pnl_in_usd
            )
            if profit_set_usd:
                logger.info(
                    f"Successfully set actual_profit_in_usd={pnl_in_usd if pnl_in_usd is not None else 'N/A'} for SELL trade DB ID {sell_order_db_id}"
                )
            else:
                logger.error(
                    f"Failed to set actual_profit_in_usd for SELL trade DB ID {sell_order_db_id}"
                )
        else:
            logger.warning(
                "sell_order_db_id not available, cannot set actual_profit or actual_profit_in_usd for the sell trade."
            )

        if original_buy_db_trade_id and original_buy_db_trade_id != "N/A":
            status_updated = update_trade_status(
                trade_id=original_buy_db_trade_id, new_status="closed"
            )
            if status_updated:
                logger.info(
                    f"Successfully updated status to 'closed' for BUY trade DB ID {original_buy_db_trade_id}"
                )
            else:
                logger.error(
                    f"Failed to update status for BUY trade DB ID {original_buy_db_trade_id}"
                )
        else:
            logger.warning(
                "original_buy_db_trade_id not available, cannot update status for the buy trade."
            )
        # --- End Database Updates ---

        # Calculate reward for Q-learning
        reward = 0
        if reason == "take_profit":
            reward = 1.0
            logger.debug(
                f"Reward +1.0 for Take Profit on trade {original_buy_exchange_id}."
            )
        elif reason == "stop_loss":
            reward = -1.0
            logger.debug(
                f"Reward -1.0 for Stop Loss on trade {original_buy_exchange_id}."
            )
        elif reason == "sell_signal":
            # Reward based on PnL for trades closed by a sell signal
            reward = (
                0.5 if pnl > 0 else (-0.5 if pnl < 0 else 0)
            )  # Small positive/negative reward for profit/loss
            logger.debug(
                f"Reward {reward} for Sell Signal exit on trade {original_buy_exchange_id} (PnL: {pnl:.6f})."
            )
        else:
            # Default reward for other reasons
            reward = 0  # Neutral reward
            logger.debug(
                f"Neutral reward for unknown exit reason '{reason}' on trade {original_buy_exchange_id}."
            )

        # Update Q-value using the state when the trade was *opened* and the action taken (buy)
        if entry_state not in ["unknown", "state_indicators_missing"]:
            logger.debug(
                f"Updating Q-table: State='{entry_state}', Action='{entry_action}', Reward={reward} for trade {original_buy_exchange_id}"
            )
            if entry_action in ["buy", "sell", "hold"]:  # Should be 'buy'
                self.q_table.update_q_value(entry_state, entry_action, reward)
            else:
                logger.warning(
                    f"Cannot update Q-table for trade {original_buy_exchange_id}: Invalid entry action '{entry_action}'."
                )
        else:
            logger.warning(
                f"Cannot update Q-table for trade {original_buy_exchange_id}: Unknown or missing entry state."
            )

        # Add the completed trade details to the history
        completed_trade: Dict[str, Any] = {
            **buy_trade_details,  # Include all original BUY trade details
            "exit_price": exit_price,
            "exit_time": datetime.now(),
            "pnl": pnl,  # This PnL is for the completed BUY-SELL cycle
            "roi": roi,  # This ROI is for the completed BUY-SELL cycle
            "exit_reason": reason,
            "closing_sell_db_id": sell_order_db_id,  # Store the DB ID of the sell order that closed this
            # 'config': self.config.model_dump() # Optional
        }
        self.trade_history.append(completed_trade)

        # Print/Log the trade completion details
        quote_currency = (
            self.config.trading_pair.split("/")[-1]
            if "/" in self.config.trading_pair
            else "???"
        )
        print(
            f"✅ TRADE CLOSED: Original BUY (Exchange ID={original_buy_exchange_id}, DB ID={original_buy_db_trade_id}), Closed by SELL (DB ID={sell_order_db_id}), Symbol={self.config.trading_pair}, ExitReason={reason}, "
            f"PnL={pnl:.6f} {quote_currency}, ROI={roi:.2f}%, Outcome={outcome}"
        )
        logger.info(
            f"Trade completed: Original BUY (ExID={original_buy_exchange_id}, DB_ID={original_buy_db_trade_id}), Closed by SELL (DB_ID={sell_order_db_id}), Symbol={self.config.trading_pair}, ExitReason={reason}, "
            f"EntryPrice={entry_price:.6f}, ExitPrice={exit_price:.6f}, "
            f"Amount={trade_amount:.6f}, PnL={pnl:.6f}, ROI={roi:.2f}%, EntryState='{entry_state}'"
        )

    def stop(self):
        """Stop the trading bot"""
        logger.info(f"Attempting to stop bot for user {self.user_id}")
        self.running = False
        if hasattr(self, "thread") and self.thread.is_alive():
            logger.info(f"Joining bot thread for user {self.user_id}...")
            self.thread.join(timeout=10)  # Give thread up to 10 seconds to finish loop
            if self.thread.is_alive():
                logger.warning(
                    f"Bot thread for user {self.user_id} did not join gracefully within timeout."
                )
            else:
                logger.info(f"Bot thread for user {self.user_id} joined successfully.")
        print(f"🛑 Stopped bot for {self.user_id}")
        self._print_report()
        self.q_table.save()  # Save Q-table on shutdown
        logger.info(f"Bot stopped and Q-table saved for user {self.user_id}.")

    @classmethod
    def get_instance(cls, user_id: str) -> Optional["TradingBot"]:
        """Get existing bot instance"""
        with cls._lock:
            return cls._instances.get(user_id)

    @classmethod
    def stop_instance(cls, user_id: str) -> bool:
        """Stop and remove bot instance"""
        with cls._lock:
            if user_id in cls._instances:
                bot = cls._instances[user_id]
                logger.info(f"Requesting stop for bot instance {user_id}")
                bot.stop()
                del cls._instances[user_id]
                logger.info(f"Bot instance {user_id} removed.")
                return True
            logger.warning(f"Stop requested for non-existent bot instance {user_id}.")
            return False
