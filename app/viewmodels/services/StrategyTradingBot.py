import random
import threading
import random
from app.viewmodels.api.kraken.KrakenAPI import KrakenAPI
from app.viewmodels.services.TradingBot import TradingConfig
from app.models.strategies import get_strategy_by_id
from app.viewmodels.services.llm import DeepSeekPPOAgent, QwenTradingAssistant, MODEL_PATHS

input_dim = 30
output_dim = 3

qwen_assistant = QwenTradingAssistant(model_path=MODEL_PATHS["qwen"]["model_path"])
ppo_agent = DeepSeekPPOAgent(
    model_path=MODEL_PATHS["ppo_agent"]["model_path"],
    input_dim=input_dim,
    output_dim=output_dim
)

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
            estado_ambiente = [0.5]*input_dim
            trading_action = ppo_agent.execute_action(qwen_output, estado_ambiente)

            print("#"*30)
            print(f"✨ trading_action: {trading_action}")
            print(f"✨ qwen_output: {qwen_output}" )
            print("#"*30)

        choices = [ qwen_output["action"] ]
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