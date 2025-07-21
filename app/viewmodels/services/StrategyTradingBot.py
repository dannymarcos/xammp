import random
import threading
import random
import time
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

class StrategyTradingBot:
    def __init__(self, user_id, exchange: Exchange, config: dict, type_wallet: str):
        self.user_id = user_id
        self.exchange = exchange
        self.running = False
        self.trades = []
        self.config = TradingConfig(**config)
        self.wallet_admin = WalletAdmin()
        self.wallet = Wallet(self.user_id)
        self.type_wallet = type_wallet

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
            decision = self.interact_with_llm(strategy)
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

        qwen_strategy = qwen_assistant.generate_strategy(
            current_market=market_data,
            strategy_prompt=strategy_prompt,
            orders_made=self.trades
        )

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
        try:
            if decision == "buy":
                self.execute_buy_order()
            elif decision == "sell":
                self.execute_sell_order()
            else:
                self.wait()
        except Exception as e:
            print(f"Error executing action: {e}")

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
            return
            
        print(f"Using current market price for transactions: {price}")
        
        # Registrar retiro en la wallet del usuario (BTC/USD) y depósito en BTC
        amount = self.config.trade_amount
        
        # Restar USDT
        self.wallet_admin.add_found(self.user_id, -price * amount, "USDT" if quote_currency == "USD" else quote_currency, "general")
        # Sumar BTC
        self.wallet_admin.add_found(self.user_id, amount, base_currency, self.type_wallet)

        self.trades.append({"action": "buy", "price": price})
        print(f"📈 BUY order executed at {price}")

    def execute_sell_order(self):
        base_currency, quote_currency = self.config.trading_pair.split("/")

        # Verificar si tiene suficiente BTC en la wallet específica
        if not self.wallet.has_balance_in_currency(self.config.trade_amount, base_currency, base_currency, self.type_wallet):
            print(f"ERROR: Insufficient {base_currency} balance in your {self.type_wallet} wallet. Required: {self.config.trade_amount}")
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
            return
            
        print(f"Using current market price for transactions: {price}")
        
        # Registrar depósito en la wallet del usuario (BTC/USD) y retiro en BTC
        amount = self.config.trade_amount
        
        # Restar BTC
        self.wallet_admin.add_found(self.user_id, -amount, base_currency, self.type_wallet)
        # Sumar USDT
        self.wallet_admin.add_found(self.user_id, price * amount, "USDT" if quote_currency == "USD" else quote_currency, "general")

        self.trades.append({"action": "sell", "price": price})
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