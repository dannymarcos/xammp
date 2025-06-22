import random
import threading
import random
from app.viewmodels.api.kraken.KrakenAPI import KrakenAPI
from app.viewmodels.services.TradingBot import TradingConfig
from app.models.strategies import get_strategy_by_id

class StrategyTradingBot:
    def __init__(self, user_id, exchange: KrakenAPI, config: dict):
        self.user_id = user_id
        self.exchange = exchange
        self.running = False
        self.trades = []
        self.config = TradingConfig(**config)

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
            import time
            time.sleep(5)
            strategy = self.get_strategy()
            market_data = self.get_market_data()
            decision = self.interact_with_llm(strategy, market_data)
            self.execute_action(decision)

    def get_strategy(self):
        # Simulate fetching a trading strategy from a database.
        return "Simple moving average crossover strategy."

    def get_market_data(self):
        # Simulate retrieving market data.
        return {"price": random.uniform(100, 200)}

    def interact_with_llm(self, strategy, market_data):
        strategy_id = self.config.strategy_id
        if not strategy_id:
            prompt = "Should I buy or sell?"
        strategy =  get_strategy_by_id(self.user_id, strategy_id)

        if not strategy:
            prompt = "Should I buy or sell?"
        else:
            prompt = strategy.text

        print(f"Prompt: {prompt}")
        choices = [ "wait"]
        return random.choice(choices)

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
        order, _ = self.exchange.add_order(order_type="market", order_direction="buy", volume=self.config.trade_amount, symbol=self.config.trading_pair)

        if 'error' in order:
            print(f"Error executing buy order: {order['error']}")
            return
        
        self.trades.append({"action": "buy", "price": order["price"]})
        print(f"📈 BUY order executed at {order['price']}")

    def execute_sell_order(self):
        order, _ = self.exchange.add_order(order_type="market", order_direction="sell", volume=self.config.trade_amount, symbol=self.config.trading_pair)

        if 'error' in order:
            print(f"Error executing sell order: {order['error']}")
            return
        
        self.trades.append({"action": "sell", "price": order["price"]})
        print(f"📉 SELL order executed at {order['price']}")

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