import logging
import random
import threading
import random
import time
from app.lib.utils.tx import emit
from app.viewmodels.services.TradingBot import TradingConfig
from app.models.strategies import get_strategy_by_id
from app.viewmodels.services.llm import DeepSeekPPOAgent, QwenTradingAssistant, MODEL_PATHS
from app.viewmodels.api.exchange.Exchange import ExchangeFactory
from app.viewmodels.api.exchange.FatherExchange import Exchange
from app.viewmodels.wallet.found import Wallet, WalletAdmin

input_dim = 30
output_dim = 3

qwen_assistant = QwenTradingAssistant(model_path=MODEL_PATHS["qwen"]["model_path"])
ppo_agent = DeepSeekPPOAgent(
    model_path=MODEL_PATHS["ppo_agent"]["model_path"],
    input_dim=input_dim,
    output_dim=output_dim
)
logger = logging.getLogger(__name__)

class StrategyTradingBot:
    def __init__(self, user_id, exchange: Exchange, config: dict, type_wallet: str, email: str):
        self.user_id = user_id
        self.exchange = exchange
        self.running = False
        self.trades = []
        self.config = TradingConfig(**config)
        self.wallet_admin = WalletAdmin()
        self.wallet = Wallet(self.user_id)
        self.type_wallet = type_wallet
        self.email = email

    def start(self):
        self.running = True
        print("Simulated trading bot started.")
        self.thread = threading.Thread(target=self.run_loop)
        self.thread.start()
        return True

    def stop(self):
        self.running = False
        print("Simulated trading bot stopped.")
        logger.info("-> SLEEP 60s")
        time.sleep(60)

        _blocked_balance_ = self.wallet.get_blocked_balance(currency="BTC/USDT", by_bot="strategy-bot")
        if _blocked_balance_["start_with"] != None:
            operation_contrary = "buy" if _blocked_balance_["start_with"] == "sell" else "sell"
            user_cryptos = self.wallet.get_blocked_balance(currency="BTC/USDT", by_bot="strategy-bot")["amount_crypto"]
            self.execute_action(operation_contrary)
            emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": f"All BTC ({abs(user_cryptos)}) has been sold."})
            emit(email=self.email, event="bot", data={"id": "refresh-balance"})

        self.generate_report()

    def run_loop(self):
        while self.running:
            time.sleep(5)
            strategy = self.get_strategy()
            emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": "Our AI assistant is analyzing the market and preparing your next trading move"})
            decision = self.interact_with_llm(strategy)
            emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": f"Our AI assistant suggests to '{decision.upper()}'"})
            self.execute_action(decision)

    def get_strategy(self):
        # Simulate fetching a trading strategy from a database.
        return "Simple moving average crossover strategy."

    def interact_with_llm(self, strategy):
        timeframe = self.config.timeframe
        # since 10 days ago
        # since = int(time.time() - (10 * 24 * 60 * 60))
        market_data = self.exchange.fetch_ohlcv_optimized(self.config.trading_pair, timeframe)
        strategy_id = self.config.strategy_id
        if not strategy_id:
            strategy_prompt = "Should I buy or sell?"
        strategy =  get_strategy_by_id(self.user_id, strategy_id)

        if not strategy:
            strategy_prompt = "Should I buy or sell?"
        else:
            strategy_prompt = strategy.text

        emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": "AI is checking your strategy. Please wait a moment."})
        qwen_strategy = qwen_assistant.generate_strategy(
            current_market=market_data,
            strategy_prompt=strategy_prompt,
            orders_made=self.trades
        )

        emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": "AI is checking the market for you..."})
        qwen_output = qwen_assistant.parse_strategy(qwen_strategy)

        if qwen_output == None:
            print("#"*30)
            print("🔴 QWEN NO RESPONDIO UN JSON")
            print("#"*30)
            return []
        else:
            action_map = {0: "buy", 1: "sell", 2: "wait"}

            estado_ambiente = [0.5]*input_dim
            trading_action = ppo_agent.execute_action(qwen_output, estado_ambiente)
            trading_action = action_map.get(int(trading_action), "wait")

            print("#"*30)
            print(f"✨ trading_action: {trading_action}")
            print(f"✨ qwen_output: {qwen_output}" )
            print("#"*30)

        return trading_action

    def execute_action(self, decision):
        # Based on the LLM's simulated decision:
        if(decision == "wait"):
            return

        amount = self.config.trade_amount

        _blocked_balance_ = self.wallet.get_blocked_balance(currency="BTC/USDT", by_bot="strategy-bot")
        if _blocked_balance_["start_with"] != None:
            operation_contrary = "buy" if _blocked_balance_["start_with"] == "sell" else "sell"
            if decision == operation_contrary:
                user_cryptos = _blocked_balance_["amount_crypto"]
                amount = user_cryptos

        data = {
            "orderType": "market",
            "orderDirection": decision,
            "amount": amount,
            "symbol": self.config.trading_pair,
            "order_made_by": "bot",
        }
        
        if self.config.basic_bot_trading_mode_full in ["kraken_spot", "kraken_futures"]:
            price_data = self.exchange.get_symbol_price(self.config.trading_pair)
            if isinstance(price_data, tuple):
                if isinstance(price_data[0], dict) and 'price' in price_data[0]:
                    price = price_data[0]['price']
                else:
                    price = price_data[0]
            else:
                price = price_data

            data["price"] = price * amount
        if self.config.basic_bot_trading_mode_full in ["kraken_futures", "bingx_spot", "bingx_futures"]:
            data["leverage"] = 1.0
            data["stopLoss"] = None
            data["takeProfit"] = None
        
        data["order_made_by"] = "strategy-bot"

        from app.lib.utils.add_order import add_order
        if self.config.basic_bot_trading_mode_full == "bingx_spot":
            user_cryptos = self.wallet.get_blocked_balance(currency="BTC/USDT", by_bot="strategy-bot")["amount_crypto"]
            if decision == "sell" and user_cryptos <= 0:
                emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": "No crypto has been purchased previously, therefore it cannot be sold"})
                return
            
        success, amount_obtained_from_the_order_crypto = add_order(user_id=self.user_id, data=data, trading_mode=self.config.basic_bot_trading_mode_full, type_bot="strategy-bot")
        if not success:
            emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": "Not enough funds (main exchange) to place your buy order"})
            return
        
        emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": f"{decision} order placed. You're all set!"})
        emit(email=self.email, event="bot", data={"id": "refresh-history-strategy-bot"})
        emit(email=self.email, event="bot", data={"id": "refresh-balance"})


    def generate_report(self):
        # Upon stopping, generate a final report summarizing simulated trades and outcomes with emojis.
        print("\n--- Trading Report ---")
        if not self.trades:
            print("No trades were executed.")
            return

        for trade in self.trades:
            action = trade["action"]
            price = trade["price"]
            if action == "buy":
                print(f"Bought at: {price} 📈")
            elif action == "sell":
                print(f"Sold at: {price} 📉")

        print("--- End Report ---")