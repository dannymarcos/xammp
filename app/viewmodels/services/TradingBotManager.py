from threading import Thread, Event
from flask import current_app
import random
import logging
import traceback
from app.models.users import User
from app.viewmodels.services.TradingBot import TradingBot
from app.viewmodels.services.StrategyTradingBot import StrategyTradingBot
from app.viewmodels.api.exchange.Exchange import ExchangeFactory

# Configure logging if not already configured
logger = logging.getLogger(__name__)


class TradingBotManager:
    _bots = {}  # Stores active bots by user_id
    _legacy_bots = {}  # Stores legacy bots for testing purposes
    exchange: ExchangeFactory = None
    type_wallet = None

    @classmethod
    def start_bot(
        cls,
        user_id,
        exchange: ExchangeFactory,
        config,
        bot_id="basic-bot",
        type_wallet: str = "",
        email: str = "",
    ):
        """
        Start a trading bot for the specified user using the TradingBot implementation

        Args:
            user_id: The user ID to start the bot for
            kraken_api: The KrakenAPI instance to use
            config: The bot configuration

        Returns:
            bool: True if the bot was started successfully, False otherwise
        """
        try:
            logger.info("[%s] 🥵 Starting bot for user %s", bot_id, user_id)

            # Check if bot is already running
            if user_id in cls._bots:
                if bot_id in cls._bots[user_id]:
                    logger.warning("Bot for user %s is already running", user_id)
                    return False

            # Get API credentials from user
            user = User.query.filter_by(id=user_id).first()
            if not user:
                logger.error("User %s not found", user_id)
                return False

            cls.exchange = exchange
            cls.type_wallet = type_wallet

            # Create and start the TradingBot
            try:
                logger.debug("Initializing TradingBot for user %s", user_id)
                    
                if bot_id == "strategy-bot":
                    bot = StrategyTradingBot(
                        user_id,
                        cls.exchange,
                        config,
                        cls.type_wallet,
                        email
                    )
                else:
                    # "basic-bot" or others
                    bot = TradingBot(
                        user_id,
                        cls.exchange,
                        config,
                        cls.type_wallet,
                        email
                    )

                logger.debug("Starting TradingBot for user %s", user_id)
                if not bot.start():
                    logger.error("Failed to start bot for user %s", user_id)
                    return False

                # Store the bot instance
                if user_id not in cls._bots:
                    cls._bots[user_id] = {}

                cls._bots[user_id][bot_id] = bot
                logger.info("Successfully started bot for user %s", user_id)
                return True

            except Exception as e:
                logger.error("Error initializing TradingBot for user %s: %s", user_id, str(e))
                logger.debug("Initialization error details: %s", traceback.format_exc())
                return False

        except Exception as e:
            logger.error("Unexpected error starting bot for user %s: %s", user_id, str(e))
            logger.debug("Error details: %s", traceback.format_exc())
            return False

    @classmethod
    def stop_bot(cls, user_id, bot_id):
        """
        Stop the trading bot for the specified user

        Args:
            user_id: The user ID to stop the bot for

        Returns:
            bool: True if the bot was stopped successfully, False otherwise
        """
        try:
            logger.info(f"Stopping bot for user {user_id}")

            # Check if bot exists
            if user_id not in cls._bots:
                cls._bots[user_id] = {}
                if bot_id not in cls._bots[user_id]:
                    logger.warning(f"No active bot {bot_id} found for user {user_id}")
                    return False

            # Get the bot instance
            bot = cls._bots[user_id][bot_id]

            # Stop the bot
            try:
                logger.debug(f"Calling stop method on bot for user {user_id}")
                bot.stop()
                logger.info(f"Successfully stopped bot for user {user_id}")

                # Remove the bot from the active bots
                del cls._bots[user_id][bot_id]
                return True

            except Exception as e:
                logger.error(f"Error stopping bot for user {user_id}: {str(e)}")
                logger.debug(f"Stop error details: {traceback.format_exc()}")
                return False

        except Exception as e:
            logger.error(f"Unexpected error stopping bot for user {user_id}: {str(e)}")
            logger.debug(f"Error details: {traceback.format_exc()}")
            return False

    @classmethod
    def is_bot_running(cls, user_id, bot_id):
        """
        Check if a bot is running for the specified user

        Args:
            user_id: The user ID to check

        Returns:
            bool: True if a bot is running for the user, False otherwise
        """
        # Check if bot exists in the new implementation
        if user_id in cls._bots:
            if bot_id in cls._bots[user_id]:
                bot = cls._bots[user_id][bot_id]
                return hasattr(bot, "running") and bot.running

        # Check if bot exists in the legacy implementation
        if user_id in cls._legacy_bots:
            if bot_id in cls._legacy_bots[user_id]:
                bot_data = cls._legacy_bots[user_id][bot_id]
                return bot_data["thread"].is_alive()

        return False

    # Legacy methods for testing purposes
    @classmethod
    def start_legacy_bot(cls, user_id, config, bot_id):
        """
        Start a legacy trading bot for testing purposes

        Args:
            user_id: The user ID to start the bot for
            kraken_api: The KrakenAPI instance to use
            config: The bot configuration

        Returns:
            bool: True if the bot was started successfully, False otherwise
        """
        try:
            logger.info("Starting legacy bot for user %s", user_id)

            # Check if bot is already running
            if user_id in cls._legacy_bots:
                if bot_id in cls._legacy_bots[user_id]:
                    logger.warning("Legacy bot for user %s is already running %s", user_id, bot_id)
                    return False

            # Get API credentials from user
            user = User.query.filter_by(id=user_id).first()
            if not user:
                logger.error("User %s not found", user_id)
                return False

            # Create and start the legacy bot
            stop_event = Event()
            bot_thread = Thread(
                target=run_trading_bot,
                args=(
                    current_app._get_current_object(),
                    cls.exchange,
                    config,
                    stop_event,
                ),
                daemon=True,
            )

            cls._legacy_bots[user_id][bot_id] = {"thread": bot_thread, "stop_event": stop_event}
            bot_thread.start()
            logger.info("Successfully started legacy bot for user %s", user_id)
            return True

        except Exception as e:
            logger.error("Error starting legacy bot for user %s: %s", user_id, str(e))
            logger.debug("Error details: %s", traceback.format_exc())
            return False

    @classmethod
    def stop_legacy_bot(cls, user_id, bot_id):
        """
        Stop a legacy trading bot

        Args:
            user_id: The user ID to stop the bot for

        Returns:
            bool: True if the bot was stopped successfully, False otherwise
        """
        try:
            logger.info(f"Stopping legacy bot for user {user_id}")

            # Check if bot exists
            if user_id not in cls._legacy_bots:
                cls._legacy_bots[user_id] = {}
                if bot_id not in cls._legacy_bots[user_id]:
                    logger.warning(f"No active legacy bot found for user {user_id} - {bot_id}")
                    return False

            # Get the bot data
            bot_data = cls._legacy_bots[user_id][bot_id]

            # Stop the bot
            bot_data["stop_event"].set()  # Signal to stop

            # Wait with timeout to prevent hanging
            bot_data["thread"].join(timeout=5.0)

            if bot_data["thread"].is_alive():
                logger.warning(
                    f"Legacy bot thread for user {user_id} didn't stop gracefully"
                )

            # Remove the bot from the active bots
            del cls._legacy_bots[user_id][bot_id]
            logger.info(f"Successfully stopped legacy bot for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error stopping legacy bot for user {user_id}: {str(e)}")
            logger.debug(f"Error details: {traceback.format_exc()}")
            return False

    @classmethod
    def stop_all_bots(cls):
        """
        Detiene todos los bots activos, tanto los nuevos como los legacy.
        """
        for user_id in list(cls._bots.keys()):
            for bot_id in list(cls._bots[user_id].keys()):
                try:
                    cls.stop_bot(user_id, bot_id)
                except Exception as e:
                    logger.error("Error al detener el bot %s para el usuario %s: %s", bot_id, user_id, str(e))

        for user_id in list(cls._legacy_bots.keys()):
            for bot_id in list(cls._legacy_bots[user_id].keys()):
                try:
                    cls.stop_legacy_bot(user_id, bot_id)
                except Exception as e:
                    logger.error("Error al detener el bot legacy %s para el usuario %s: %s", bot_id, user_id, str(e))
        
        logger.info("Todos los bots han sido detenidos.")


def run_trading_bot(
    app, exchange, config, stop_event
):
    """
    Legacy trading bot implementation for testing purposes

    Args:
        app: The Flask application context
        kraken_api: The KrakenAPI instance to use
        api_key: The Kraken API key
        api_secret: The Kraken API secret
        config: The bot configuration
        stop_event: The event to signal when the bot should stop
    """
    with app.app_context():
        logger.info("Legacy bot started with config: %s", config)

        try:
            while not stop_event.is_set():  # Critical check
                logger.debug("Legacy bot cycle started")

                if random.random() > 0.5:
                    exchange.add_order(
                        order_type="limit",
                        order_direction="buy",
                        volume=5,
                        symbol="XBTUSD",
                        price=5,
                    )
                    logger.info("Legacy bot would place buy order")
                else:
                    logger.info("Legacy bot would place sell order")

                # Use wait() instead of sleep() to allow immediate stopping
                stop_event.wait(timeout=1)  # Checks event every second

        except Exception as e:
            logger.error("Legacy bot error: %s", str(e))
            logger.debug("Error details: %s", traceback.format_exc())
        finally:
            logger.info("Legacy bot stopped cleanly")
