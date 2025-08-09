import logging
import random
import threading
import random
import time
from app.lib.utils.add_order import add_order
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
        self.generate_report()

    def run_loop(self):
        while self.running:
            time.sleep(5)
            strategy = self.get_strategy()
            emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": "Our AI assistant is analyzing the market and preparing your next trading move"})
            decision = self.interact_with_llm(strategy)
            emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": f"Our AI assistant suggests to '{decision.upper()}'"})
            self.execute_action("buy")

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

        data = {
            "orderType": "market",
            "orderDirection": decision,
            "amount": self.config.trade_amount,
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

            data["price"] = price * self.config.trade_amount
        if self.config.basic_bot_trading_mode_full in ["kraken_futures", "bingx_spot", "bingx_futures"]:
            data["leverage"] = 1.0
            data["stopLoss"] = None
            data["takeProfit"] = None

        success = add_order(user_id=self.user_id, data=data, trading_mode=self.config.basic_bot_trading_mode_full)
        if not success:
            emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": "Not enough funds (main exchange) to place your buy order"})
            return
        
        emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": f"Buy order placed. You're all set!"})
        
    def execute_buy_order(self):
        base_currency, quote_currency = self.config.trading_pair.split("/")
        
        # Verificar si tiene suficiente USDT para comprar BTC
        # Necesitamos calcular cuánto USDT costará la operación
        current_price = self.exchange.get_symbol_price(self.config.trading_pair)
        if isinstance(current_price, tuple):
            price_data = current_price[0]
            if isinstance(price_data, dict) and "price" in price_data:
                price = price_data["price"]
            else:
                price = price_data
        else:
            price = current_price
            
        # Ensure price is a number
        if not isinstance(price, (int, float)) or price <= 0:
            print(f"ERROR: Invalid price received: {price}")
            return
            
        total_cost_usdt = self.config.trade_amount * price
        
        # Verificar si tiene suficiente USDT en la wallet general
        if not self.wallet.has_balance_in_currency(total_cost_usdt, "USDT", "USDT", "general"):
            print(f"ERROR: Insufficient USDT balance in your wallet. Required: {total_cost_usdt} USDT")
            emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": f"Not enough USDT to buy. You need {total_cost_usdt:.2f} USDT."})

            return

        # Call add_order with correct parameters based on exchange type
        try:
            # Try the futures-style call first
            order_result = self.exchange.add_order(
                order_type="market",
                order_direction="buy",
                volume=self.config.trade_amount,
                symbol=self.config.trading_pair,
                order_made_by="bot"
            )
        except TypeError:
            # If that fails, try the spot-style call
            try:
                order_result = self.exchange.add_order(
                    order_direction="buy",
                    symbol=self.config.trading_pair,
                    volume=self.config.trade_amount,
                    order_type="market",
                    order_made_by="bot"
                )
            except TypeError:
                # If both fail, try the most basic call
                order_result = self.exchange.add_order(
                    "buy",
                    self.config.trading_pair,
                    self.config.trade_amount
                )
        
        # Handle tuple response (order_data, status_code)
        if isinstance(order_result, tuple):
            order, status_code = order_result
        else:
            order = order_result
            status_code = 200

        if 'error' in order:
            print(f"Error executing buy order: {order['error']}")
            emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": "Not enough funds (main exchange) to place your buy order"})
            return
        
        # Obtener el precio actual del exchange para las transacciones
        print("Getting current price from exchange for wallet transactions...")
        current_price = self.exchange.get_symbol_price(self.config.trading_pair)
        if isinstance(current_price, tuple):
            price_data = current_price[0]
            if isinstance(price_data, dict) and "price" in price_data:
                price = price_data["price"]
            else:
                price = price_data
        else:
            price = current_price
        
        # Ensure price is a number
        if not isinstance(price, (int, float)) or price <= 0:
            print(f"ERROR: Could not get valid price from exchange: {price}")
            emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": "Sorry, we couldn't get the latest price"})
            return
            
        print(f"Using current market price for transactions: {price}")
        
        # Registrar retiro en la wallet del usuario (BTC/USD) y depósito en BTC
        amount = self.config.trade_amount
        
        # Restar USDT
        self.wallet_admin.add_found(self.user_id, -price * amount, "USDT" if quote_currency == "USD" else quote_currency, "general")
        # Sumar BTC
        self.wallet_admin.add_found(self.user_id, amount, base_currency, self.type_wallet)

        self.trades.append({"action": "buy", "price": price})
        emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": f"Buy order placed at {price}. You're all set!"})

        print(f"📈 BUY order executed at {price}")

    def execute_sell_order(self):
        base_currency, quote_currency = self.config.trading_pair.split("/")

        # Verificar si tiene suficiente BTC en la wallet específica
        if not self.wallet.has_balance_in_currency(self.config.trade_amount, base_currency, base_currency, self.type_wallet):
            print(f"ERROR: Insufficient {base_currency} balance in your {self.type_wallet} wallet. Required: {self.config.trade_amount}")
            emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": f"Not enough {base_currency} in your {self.type_wallet} wallet to sell"})

            return

        # Call add_order with correct parameters based on exchange type
        try:
            # Try the futures-style call first
            order_result = self.exchange.add_order(
                order_type="market",
                order_direction="sell",
                volume=self.config.trade_amount,
                symbol=self.config.trading_pair,
                order_made_by="bot"
            )
        except TypeError:
            # If that fails, try the spot-style call
            try:
                order_result = self.exchange.add_order(
                    order_direction="sell",
                    symbol=self.config.trading_pair,
                    volume=self.config.trade_amount,
                    order_type="market",
                    order_made_by="bot"
                )
            except TypeError:
                # If both fail, try the most basic call
                order_result = self.exchange.add_order(
                    "sell",
                    self.config.trading_pair,
                    self.config.trade_amount
                )
        
        # Handle tuple response (order_data, status_code)
        if isinstance(order_result, tuple):
            order, status_code = order_result
        else:
            order = order_result
            status_code = 200

        if 'error' in order:
            print(f"Error executing sell order: {order['error']}")
            emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": "Oops! We couldn't place your sell order"})

            return
        
        # Obtener el precio actual del exchange para las transacciones
        print("Getting current price from exchange for wallet transactions...")
        current_price = self.exchange.get_symbol_price(self.config.trading_pair)
        if isinstance(current_price, tuple):
            price_data = current_price[0]
            if isinstance(price_data, dict) and "price" in price_data:
                price = price_data["price"]
            else:
                price = price_data
        else:
            price = current_price
        
        # Ensure price is a number
        if not isinstance(price, (int, float)) or price <= 0:
            print(f"ERROR: Could not get valid price from exchange: {price}")
            emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": "Sorry, couldn't get the price"})

            return
            
        print(f"Using current market price for transactions: {price}")
        
        # Registrar depósito en la wallet del usuario (BTC/USD) y retiro en BTC
        amount = self.config.trade_amount
        
        # Restar BTC
        self.wallet_admin.add_found(self.user_id, -amount, base_currency, self.type_wallet)
        # Sumar USDT
        self.wallet_admin.add_found(self.user_id, price * amount, "USDT" if quote_currency == "USD" else quote_currency, "general")

        self.trades.append({"action": "sell", "price": price})
        emit(email=self.email, event="bot", data={"id": "strategy-bot", "msg": f"Sold at {price} 📉"})
        print(f"📉 SELL order executed at {price}")

    def wait(self):
        # Reiterate the loop.
        print("Waiting for a better opportunity.")

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