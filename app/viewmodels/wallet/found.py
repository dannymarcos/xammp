from app.viewmodels.api.exchange.Kraken.KrakenAPIFutures import KrakenFuturesExchange
from app.viewmodels.api.exchange.Bingx.BingxExchange import BingxExchange
from app.viewmodels.api.exchange.Kraken.KrakenSpotExchange import KrakenSpotExchange
from app.models.transaction_wallet import FoundWallet, create_found_wallet
from app.models.wallet import add_found_wallet, get_balance_by_currency, get_found_wallets_by_user
from app.models.trades import Trade
from app.models.users import User
from app.models.performance_aegis import PerformanceAegis
from app.viewmodels.api.exchange.Exchange import ExchangeFactory
from app.config import config
from datetime import datetime, timedelta
import threading

def get_crypto_price_in_usdt(currency: str, exchange_name: str) -> float:
    """
    Get the current price of a cryptocurrency in USDT
    Args:
        currency: The cryptocurrency symbol (e.g., "BTC", "ETH", "ZUSD", "XXBT")
        exchange_name: The exchange name (e.g., "kraken_spot", "bingx_spot")
    Returns:
        float: The price in USDT, or None if not available
    """
    try:
        # Handle Kraken's special prefixes
        if "kraken" in exchange_name:
            # Kraken uses special prefixes: Z for fiat, X for crypto
            if currency.startswith("Z"):
                # Fiat currency (ZUSD, ZEUR, etc.)
                clean_currency = currency[1:]  # Remove Z prefix
                if clean_currency in ["USD", "USDT"]:
                    return 1.0
                # For other fiat currencies, we might need conversion rates
                return None
            elif currency.startswith("X"):
                # Crypto currency (XXBT, XETH, etc.)
                clean_currency = currency[1:]  # Remove X prefix
                if clean_currency == "XBT":
                    clean_currency = "BTC"  # Kraken uses XBT for Bitcoin
            else:
                clean_currency = currency
        else:
            clean_currency = currency
        
        # Skip if currency is already USDT or USD
        if clean_currency.upper() in ["USDT", "USD"]:
            return 1.0
        
        # Determine which exchange to use for price fetching
        if "kraken" in exchange_name:
            if "futures" in exchange_name:
                exchange = ExchangeFactory().create_exchange(name="kraken_future", user_id="master")
            else:
                exchange = ExchangeFactory().create_exchange(name="kraken_spot", user_id="master")
        elif "bingx" in exchange_name:
            exchange = ExchangeFactory().create_exchange(name="bingx", user_id="master")
        else:
            # Default to Kraken spot for other exchanges
            exchange = ExchangeFactory().create_exchange(name="kraken_spot", user_id="master")
        
        # Create trading pair symbol
        symbol = f"{clean_currency}/USDT"
        
        # Get current price
        price_data = exchange.get_symbol_price(symbol)
        
        if isinstance(price_data, tuple):
            price = price_data[0]
        elif isinstance(price_data, dict) and "price" in price_data:
            price = price_data["price"]
        else:
            price = price_data
            
        if price and price > 0:
            return float(price)
        else:
            return None
            
    except Exception as e:
        print(f"Error getting price for {currency} on {exchange_name}: {e}")
        return None

class Wallet:
    def __init__(self, user_id: str):
        self.user_id = user_id

    def get_found_wallets(self, exchange: str = "general"):
        resultQuery = FoundWallet.query.filter_by(user_id=self.user_id).all()
        founds = [f.serialize for f in resultQuery]

        return founds

    def deposit_found_wallet(self, amount: float, currency: str, ref: str, red: str, exchange: str = "general", x: bool = False, verification: bool = False):
        result = create_found_wallet(self.user_id, amount, currency, ref, red, "deposit", x, verification);

        if result is None:
            return False
        
        return True


    def withdrawal_found_wallet(self, amount: float, currency: str, ref: str, red: str, exchange: str = "general", x: bool = False, verification: bool = False, capital_part: float = None):
        # Pasar capital_part a create_found_wallet
        result = create_found_wallet(
            self.user_id, 
            amount, 
            currency, 
            ref, 
            red, 
            "withdrawal", 
            x, 
            verification,
            capital_part=capital_part
        )

        if result is None:
            return False
        
        return True

    def get_pending_withdrawals(self):
        pending_withdrawals = FoundWallet.query.filter_by(
            user_id=self.user_id, 
            transaction_type="withdrawal", 
            verification=False
        ).all()

        return pending_withdrawals

    def get_pending_withdrawal_balance(self, currency: str = "USDT"):
        try:
            # Get all unverified withdrawal transactions for this currency
            pending_withdrawals = FoundWallet.query.filter_by(
                user_id=self.user_id, 
                currency=currency, 
                transaction_type="withdrawal",
                verification=False
            ).all()
            
            # Sum all pending withdrawal amounts
            total_pending = sum(withdrawal.amount for withdrawal in pending_withdrawals)
            
            return total_pending
        except Exception as e:
            print(f"Error getting pending withdrawal balance: {e}")
            return 0

    def get_balance(self, exchange: str = None):
        return get_found_wallets_by_user(self.user_id, exchange)
    
    def get_balance_by_currency(self, currency: str, exchange_name: str = None):
        return get_balance_by_currency(self.user_id, currency, exchange_name)

    def get_initial_capital(self, currency: str = "USDT"):
        """
        Get the initial capital (last deposit) for a specific currency
        Args:
            currency: The currency to check (default: USDT)
        Returns:
            float: The amount of the last deposit, or 0 if no deposits found
        """
        try:
            # Get the last deposit transaction for this currency
            last_deposit = FoundWallet.query.filter_by(
                user_id=self.user_id, 
                currency=currency, 
                transaction_type="deposit",
                verification=True
            ).order_by(FoundWallet.time.desc()).first()
            
            return last_deposit.amount if last_deposit else 0
        except Exception as e:
            print(f"Error getting initial capital: {e}")
            return 0

    def get_pending_balance(self, currency: str = "USDT"):
        """
        Get the pending balance (unverified deposits) for a specific currency
        Args:
            currency: The currency to check (default: USDT)
        Returns:
            float: The sum of all unverified deposit amounts, or 0 if no pending deposits found
        """
        try:
            # Get all unverified deposit transactions for this currency
            pending_deposits = FoundWallet.query.filter_by(
                user_id=self.user_id, 
                currency=currency, 
                transaction_type="deposit",
                verification=False
            ).all()
            
            # Sum all pending deposit amounts
            total_pending = sum(deposit.amount for deposit in pending_deposits)
            
            return total_pending
        except Exception as e:
            print(f"Error getting pending balance: {e}")
            return 0

    def get_accumulated_performance(self, currency: str = "USDT"):
        """
        Calculate accumulated performance (gains/losses) from trading activities
        Args:
            currency: The currency to check (default: USDT)
        Returns:
            dict: Contains total_gains, total_losses, net_performance, and performance_percentage
        """
        try:
            # Get all trades for this user
            all_trades = Trade.query.filter_by(user_id=self.user_id).order_by(Trade.timestamp.asc()).all()
            
            total_gains = 0
            total_losses = 0
            position_trades = {}  # Track open positions by symbol
            
            for trade in all_trades:
                symbol = trade.symbol
                direction = trade.order_direction
                volume = trade.volume
                price = trade.price
                
                # Calculate the value in USD (since price is already in USD for futures)
                trade_value = volume * price
                
                if symbol not in position_trades:
                    position_trades[symbol] = []
                
                if direction == "buy":
                    # Add to position
                    position_trades[symbol].append({
                        'volume': volume,
                        'price': price,
                        'value': trade_value
                    })
                elif direction == "sell":
                    # Calculate P&L for this sell
                    if position_trades[symbol]:
                        # Use FIFO method to calculate P&L
                        remaining_volume = volume
                        total_cost = 0
                        total_volume_bought = 0
                        
                        # Calculate average cost from buy trades
                        for buy_trade in position_trades[symbol]:
                            if remaining_volume <= 0:
                                break
                            
                            volume_to_use = min(remaining_volume, buy_trade['volume'])
                            total_cost += volume_to_use * buy_trade['price']
                            total_volume_bought += volume_to_use
                            remaining_volume -= volume_to_use
                        
                        if total_volume_bought > 0:
                            avg_cost = total_cost / total_volume_bought
                            sell_value = volume * price
                            cost_value = volume * avg_cost
                            pnl = sell_value - cost_value
                            
                            if pnl > 0:
                                total_gains += pnl
                            else:
                                total_losses += abs(pnl)
            
            # Calculate net performance
            net_performance = total_gains - total_losses
            
            # Get initial capital from wallet deposits
            initial_capital = self.get_initial_capital(currency)
            
            # Calculate performance percentage
            performance_percentage = 0
            if initial_capital > 0:
                performance_percentage = (net_performance / initial_capital) * 100
            
            return {
                "total_gains": total_gains,
                "total_losses": total_losses,
                "net_performance": net_performance,
                "performance_percentage": performance_percentage,
                "initial_capital": initial_capital
            }
            
        except Exception as e:
            print(f"Error calculating accumulated performance: {e}")
            return {
                "total_gains": 0,
                "total_losses": 0,
                "net_performance": 0,
                "performance_percentage": 0,
                "initial_capital": 0
            }

    def get_chart_data(self, days: int = 30):
        """
        Get daily gains and losses data for chart visualization
        Args:
            days: Number of days to look back (default: 30)
        Returns:
            dict: Contains labels, earnings_data, and losses_data for Chart.js
        """
        try:
            # Get trades from the specified number of days ago
            start_date = datetime.now() - timedelta(days=days)
            
            # Get trades from the specified number of days ago
            trades = Trade.query.filter(
                Trade.user_id == self.user_id,
                Trade.timestamp >= start_date,
                Trade.timestamp <= datetime.now()
            ).order_by(Trade.timestamp.asc()).all()
            
            # Initialize data structures for daily tracking
            daily_data = {}
            labels = []
            earnings_data = []
            losses_data = []
            
            # Generate date labels for the last 'days' days
            for i in range(days):
                date = (datetime.now() - timedelta(days=days-1-i)).strftime('%Y-%m-%d')
                labels.append(date)
                daily_data[date] = {'gains': 0, 'losses': 0}
            
            # Process trades and calculate daily P&L
            position_trades = {}  # Track open positions by symbol
            
            for trade in trades:
                symbol = trade.symbol
                direction = trade.order_direction
                volume = trade.volume
                price = trade.price
                trade_date = trade.timestamp.strftime('%Y-%m-%d')
                
                # Skip if trade date is not in our range
                if trade_date not in daily_data:
                    continue
                
                # Calculate the value in USD
                trade_value = volume * price
                
                if symbol not in position_trades:
                    position_trades[symbol] = []
                
                if direction == "buy":
                    # Add to position
                    position_trades[symbol].append({
                        'volume': volume,
                        'price': price,
                        'value': trade_value
                    })
                elif direction == "sell":
                    # Calculate P&L for this sell
                    if position_trades[symbol]:
                        # Use FIFO method to calculate P&L
                        remaining_volume = volume
                        total_cost = 0
                        total_volume_bought = 0
                        
                        # Calculate average cost from buy trades
                        for buy_trade in position_trades[symbol]:
                            if remaining_volume <= 0:
                                break
                            
                            volume_to_use = min(remaining_volume, buy_trade['volume'])
                            total_cost += volume_to_use * buy_trade['price']
                            total_volume_bought += volume_to_use
                            remaining_volume -= volume_to_use
                        
                        if total_volume_bought > 0:
                            avg_cost = total_cost / total_volume_bought
                            sell_value = volume * price
                            cost_value = volume * avg_cost
                            pnl = sell_value - cost_value
                            
                            # Add to daily data
                            if pnl > 0:
                                daily_data[trade_date]['gains'] += pnl
                            else:
                                daily_data[trade_date]['losses'] += abs(pnl)
            
            # Convert daily data to arrays for Chart.js
            for date in labels:
                earnings_data.append(daily_data[date]['gains'])
                losses_data.append(daily_data[date]['losses'])
            
            return {
                "labels": labels,
                "earnings_data": earnings_data,
                "losses_data": losses_data
            }
            
        except Exception as e:
            print(f"Error getting chart data: {e}")
            return {
                "labels": [],
                "earnings_data": [],
                "losses_data": []
            }

    def has_balance_in_currency(self, amount: float, symbol_base: str, symbol_compare: str, exchange_name: str, type_exchange: str = "kraken_spot") -> bool:
        """
        Check if the user has the specified amount in symbol_compare
        Args:
            amount: The amount to check
            symbol_base: The currency symbol (e.g., "BTC")
            exchange_name: type wallet (general, kraken_futures, bingx_futures, etc...)
        Returns:
            bool: True if user has sufficient symbol_compare balance, False otherwise
        """
        try:
            # Si la moneda ya es USDT, hacer comparación directa
            if symbol_base.upper() == symbol_compare.upper():
                balance = self.get_balance_by_currency(symbol_base, exchange_name)

                return balance >= amount
            
            exchange = ExchangeFactory().create_exchange(name=type_exchange, user_id=self.user_id)
            trading_pair = f"{symbol_base}/{symbol_compare}"
            price_data = exchange.get_symbol_price(trading_pair) # = ({'price': 107735.4}, 200)

            # Extract price from the response
            if isinstance(price_data, tuple):
                current_price = price_data[0]  # Get the first element (price dict)
                if isinstance(current_price, dict) and "price" in current_price:
                    current_price = current_price["price"]  # Extract the actual price value
                else:
                    current_price = price_data[0]  # If it's not a dict, use it directly
            elif isinstance(price_data, dict) and "price" in price_data:
                current_price = price_data["price"]
            else:
                current_price = price_data

            print(f"current_price: {current_price}")
            print("#"*80)
            
            if current_price is None or current_price <= 0:
                print(f"Error: Could not get price for {trading_pair}")
                return False
            
            # Calcular el valor en USDT
            value_in_usdt = amount * current_price
            
            # Obtener balance actual de USDT
            print("#"*80)
            print(f"value_in_usdt: {value_in_usdt}")
            usdt_balance = self.get_balance_by_currency(symbol_compare, exchange_name)
            print(f"usdt_balance: {usdt_balance}")
            print(f"usdt_balance >= value_in_usdt: {usdt_balance >= value_in_usdt}")
            print("#"*80)            
            return usdt_balance >= value_in_usdt
            
        except Exception as e:
            print(f"Error checking {symbol_compare} balance: {e}")
            return False




    def get_total_deposits(self):
        """Obtiene solo la suma de los depósitos verificados (sin incluir saldos actuales)"""
        deposits = FoundWallet.query.filter_by(
            user_id=self.user_id,
            verification=True,
            transaction_type="deposit",
            x=False
        ).all()
        return sum(f.amount for f in deposits)
    
    def get_total_withdrawn_capital(self):
        """Obtiene la suma de todas las partes de capital retiradas"""
        withdrawals = FoundWallet.query.filter_by(
            user_id=self.user_id,
            verification=True,
            transaction_type="withdrawal"
        ).all()
        
        total_capital = 0.0
        for w in withdrawals:
            if w.capital_part is not None:
                total_capital += w.capital_part
            else:
                # Para retiros antiguos sin capital_part, asumimos que son 100% capital
                total_capital += w.amount
        return total_capital

    def get_capital_base(self):
        """Calcula el capital base dinámicamente"""
        total_deposits = self.get_total_deposits()
        total_withdrawn_capital = self.get_total_withdrawn_capital()
        return max(0, total_deposits - total_withdrawn_capital)
    
    def get_real_performance(self):
        """Calcula el rendimiento real considerando todos los exchanges"""
        exchanges = ["general", "kraken_spot", "kraken_futures", "bingx_spot", "bingx_futures"]
        amount_total_now = 0.0

        for exchange in exchanges:
            try:
                # Obtener todos los balances para este exchange
                balance_wallets = get_found_wallets_by_user(self.user_id, exchange)
                
                for wallet in balance_wallets:
                    currency = wallet.get("currency")
                    amount = wallet.get("amount", 0)
                    
                    if currency and amount > 0:
                        # Obtener precio específico para el exchange
                        price_usdt = get_crypto_price_in_usdt(currency, exchange)
                        
                        if price_usdt and price_usdt > 0:
                            usdt_equivalent = amount * price_usdt
                            amount_total_now += usdt_equivalent
                        elif currency.upper() in ["USDT", "USD"]:
                            # Manejar monedas estables directamente
                            amount_total_now += amount
                        else:
                            print(f"Warning: Could not get USDT price for {currency} on {exchange}")
                            
            except Exception as e:
                print(f"Error getting balance for exchange {exchange}: {e}")
                continue
        
        # Calcular capital base
        capital_base = self.get_capital_base()
        
        # Calcular ganancias disponibles (puede ser negativa si hay pérdidas)
        available_gain = amount_total_now - capital_base
        
        return available_gain, amount_total_now, None


class WalletAdmin:
    def __init__(self):
        pass

    def get_list_founds(self, page: int):
        resultQuery = FoundWallet.query.filter_by(x=False).order_by(FoundWallet.time.desc()).paginate(page=page, per_page=50, error_out=False).items
        
        # Get serialized data and add user email
        transactions = []
        for transaction in resultQuery:
            transaction_data = transaction.serialize
            
            # Get user email using the user_id from the transaction
            user = User.query.filter_by(id=transaction.user_id).first()
            transaction_data['user_email'] = user.email if user else 'Unknown'
            
            transactions.append(transaction_data)
        
        return transactions
    
    def set_verification(self, id: str, value: bool):
        wallet = FoundWallet.query.filter_by(id=id).first()

        if wallet:
            wallet.verification = value
            wallet.save()
        else:
            return False
        
        return True

    def set_verification_with_tx_hash(self, id: str, value: bool, tx_hash: str):
        """
        Set verification status and store transaction hash for withdrawal processing
        Args:
            id: Transaction ID
            value: Verification status (True/False)
            tx_hash: Transaction hash from blockchain
        Returns:
            bool: True if successful, False otherwise
        """
        wallet = FoundWallet.query.filter_by(id=id).first()

        if wallet:
            wallet.verification = value
            wallet.tx_hash = tx_hash
            wallet.save()
        else:
            return False
        
        return True
    
    def add_found(self, user_id: str, amount: float, currency: str, exchange: str = "general"):
        add_found_wallet(user_id, amount, currency, exchange)

    def get_data_with_id(self, id: str):
        wallet = FoundWallet.query.filter_by(id=id).first()

        return wallet

    def deduct_from_wallet(self, user_id: str, amount: float, currency: str, exchange: str = "general"):
        """
        Deduct amount from user's wallet balance
        Args:
            user_id: The user ID
            amount: Amount to deduct
            currency: Currency to deduct
            exchange: Exchange name (default: "general")
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            from app.models.wallet import WalletBD
            from app.models.create_db import db
            
            # Find the user's wallet for this currency and exchange
            wallet = WalletBD.query.filter_by(
                user_id=user_id, 
                currency=currency, 
                exchange=exchange
            ).first()
            
            if wallet and wallet.amount >= amount:
                # Deduct the amount
                wallet.amount -= amount
                
                # If balance becomes zero or negative, delete the wallet entry
                if wallet.amount <= 0:
                    db.session.delete(wallet)
                
                db.session.commit()
                return True
            else:
                print(f"Insufficient balance for user {user_id}, currency {currency}, exchange {exchange}")
                return False
                
        except Exception as e:
            print(f"Error deducting from wallet: {e}")
            db.session.rollback()
            return False

    def get_master_account_balances(self):
        """
        Get total balances for each exchange (master account balances)
        Returns:
            dict: Dictionary with exchange names as keys and total USDT balances as values
        """
        try:
            exchanges = ["general", "kraken_spot", "kraken_futures", "bingx_spot", "bingx_futures"]
            exchange_balances = {}
            
            for exchange in exchanges:
                # Get all balances for this exchange
                balances = get_found_wallets_by_user("master", exchange)
                
                # Sum all USDT balances for this exchange
                total_balance = 0
                for balance in balances:
                    if balance.get('currency') == 'USDT':
                        total_balance += balance.get('amount', 0)
                
                exchange_balances[exchange] = total_balance
            
            return exchange_balances
        except Exception as e:
            print(f"Error getting master account balances: {e}")
            return {
                "general": 0,
                "kraken_spot": 0,
                "kraken_futures": 0,
                "bingx_spot": 0,
                "bingx_futures": 0
            }

    def get_real_master_account_balances(self):
        """
        Get real account balances directly from exchange APIs for master accounts using parallel requests
        Returns:
            dict: Dictionary with exchange names as keys and balance data from APIs
        """
        # Initialize with default values
        real_balances = {
            "kraken_spot": {"error": "Not configured", "balances": []},
            "kraken_futures": {"error": "Not configured", "balances": []},
            "bingx_spot": {"error": "Not configured", "balances": []},
            "bingx_futures": {"error": "Not configured", "balances": []}
        }
        
        try:
            # Get API credentials from environment
            KRAKEN_API_KEY = config.KRAKEN_API_KEY
            KRAKEN_API_SECRET = config.KRAKEN_API_SECRET
            KRAKEN_FUTURE_API_KEY = config.KRAKEN_FUTURE_API_KEY
            KRAKEN_FUTURE_API_SECRET = config.KRAKEN_FUTURE_API_SECRET
            BINGX_API_KEY = config.BINGX_API_KEY
            BINGX_API_SECRET = config.BINGX_API_SECRET
            BINGX_API_KEY_FUTURES = config.BINGX_API_KEY_FUTURES
            BINGX_API_SECRET_FUTURES = config.BINGX_API_SECRET_FUTURES
            
            # Define worker functions for each exchange type
            def fetch_kraken_spot():
                try:
                    exchange = KrakenSpotExchange(user_id="master")
                    spot_balance_data, status = exchange.get_account_balance()
                    balances = []
                    if status == 200 and isinstance(spot_balance_data, dict):
                        # El resultado real está en spot_balance_data['result']
                        result = spot_balance_data.get('result', {})
                        for currency, amount in result.items():
                            balances.append({
                                "currency": currency,
                                "amount": float(amount)
                            })
                        real_balances["kraken_spot"] = {
                            "error": None,
                            "balances": balances,
                            "raw_data": spot_balance_data
                        }
                    else:
                        real_balances["kraken_spot"] = {
                            "error": f"API Error: {spot_balance_data.get('error', 'Unknown error')}",
                            "balances": []
                        }
                except Exception as e:
                    real_balances["kraken_spot"] = {
                        "error": f"Exception: {str(e)}",
                        "balances": []
                    }

            def fetch_kraken_futures():
                try:
                    exchange = KrakenFuturesExchange()
                    balance_data = exchange.get_account_balance()
                    
                    if isinstance(balance_data, list):
                        balances_with_prices = []
                        for balance in balance_data:
                            # price_usdt = get_crypto_price_in_usdt(balance.get("currency"), "kraken_futures")
                            balance_with_price = balance.copy()
                            # balance_with_price["price_usdt"] = price_usdt
                            balances_with_prices.append(balance_with_price)
                        
                        real_balances["kraken_futures"] = {
                            "error": None,
                            "balances": balances_with_prices,
                            "raw_data": balance_data
                        }
                    elif isinstance(balance_data, dict) and "error" in balance_data:
                        real_balances["kraken_futures"] = {
                            "error": f"API Error: {balance_data['error']}",
                            "balances": []
                        }
                    else:
                        real_balances["kraken_futures"] = {
                            "error": "Unexpected response format",
                            "balances": []
                        }
                except Exception as e:
                    real_balances["kraken_futures"] = {
                        "error": f"Exception: {str(e)}",
                        "balances": []
                    }

            def fetch_bingx_spot():
                try:
                    exchange = BingxExchange(trading_mode="spot")
                    balance_data = exchange.get_account_balance()
                    
                    if isinstance(balance_data, list):
                        balances_with_prices = []
                        cryptos = []
                        for balance in balance_data:
                            cryptos.append(balance.get("currency"))
                        
                        # cryptos_prices = exchange.get_all_prices(cryptos)
                        # price_usdt = get_bulk_crypto_prices(balance.get("currency"), "bingx_spot")
                        
                        for balance in balance_data:
                            balance_with_price = balance.copy()
                            # balance_with_price["price_usdt"] = cryptos_prices[balance.get("currency")]
                            balances_with_prices.append(balance_with_price)
                        
                        real_balances["bingx_spot"] = {
                            "error": None,
                            "balances": balances_with_prices,
                            "raw_data": balance_data
                        }
                    elif isinstance(balance_data, dict) and "error" in balance_data:
                        real_balances["bingx_spot"] = {
                            "error": f"API Error: {balance_data['error']}",
                            "balances": []
                        }
                    else:
                        real_balances["bingx_spot"] = {
                            "error": "Unexpected response format",
                            "balances": []
                        }
                except Exception as e:
                    real_balances["bingx_spot"] = {
                        "error": f"Exception: {str(e)}",
                        "balances": []
                    }

            def fetch_bingx_futures():
                try:
                    exchange = BingxExchange(trading_mode="swap")
                    balance_data = exchange.get_account_balance()
                    
                    if isinstance(balance_data, list):
                        balances_with_prices = []
                        for balance in balance_data:
                            # price_usdt = get_crypto_price_in_usdt(balance.get("currency"), "bingx_futures")
                            balance_with_price = balance.copy()
                            # balance_with_price["price_usdt"] = price_usdt
                            balances_with_prices.append(balance_with_price)
                        
                        real_balances["bingx_futures"] = {
                            "error": None,
                            "balances": balances_with_prices,
                            "raw_data": balance_data
                        }
                    elif isinstance(balance_data, dict) and "error" in balance_data:
                        real_balances["bingx_futures"] = {
                            "error": f"API Error: {balance_data['error']}",
                            "balances": []
                        }
                    else:
                        real_balances["bingx_futures"] = {
                            "error": "Unexpected response format",
                            "balances": []
                        }
                except Exception as e:
                    real_balances["bingx_futures"] = {
                        "error": f"Exception: {str(e)}",
                        "balances": []
                    }

            # Create and start threads for configured exchanges
            threads = []
            
            if KRAKEN_API_KEY and KRAKEN_API_SECRET:
                t = threading.Thread(target=fetch_kraken_spot)
                t.start()
                threads.append(t)
            
            if KRAKEN_FUTURE_API_KEY and KRAKEN_FUTURE_API_SECRET:
                t = threading.Thread(target=fetch_kraken_futures)
                t.start()
                threads.append(t)
            
            if BINGX_API_KEY and BINGX_API_SECRET:
                t = threading.Thread(target=fetch_bingx_spot)
                t.start()
                threads.append(t)
            
            if BINGX_API_KEY_FUTURES and BINGX_API_SECRET_FUTURES:
                t = threading.Thread(target=fetch_bingx_futures)
                t.start()
                threads.append(t)

            for t in threads:
                t.join()
            
            return real_balances
            
        except Exception as e:
            print(f"Error getting real master account balances: {e}")
            return {
                "kraken_spot": {"error": f"General error: {str(e)}", "balances": []},
                "kraken_futures": {"error": f"General error: {str(e)}", "balances": []},
                "bingx_spot": {"error": f"General error: {str(e)}", "balances": []},
                "bingx_futures": {"error": f"General error: {str(e)}", "balances": []}
            }

    def get_real_master_balance_summary(self):
        """
        Get a summary of real master account balances with total USDT values
        Returns:
            dict: Summary with total USDT balance per exchange and overall total
        """
        real_balances = self.get_real_master_account_balances()
        summary = {
            "exchanges": {},
            "total_usdt": 0,
            "last_updated": datetime.now().isoformat()
        }
        
        for exchange_name, balance_data in real_balances.items():
            exchange_summary = {
                "total_usdt": 0,
                "currencies": {},
                "error": balance_data.get("error"),
                "has_error": balance_data.get("error") is not None
            }
            
            if not balance_data.get("error"):
                for balance in balance_data.get("balances", []):
                    currency = balance.get("currency", "").upper()
                    amount = float(balance.get("amount", 0))
                    price_usdt = balance.get("price_usdt")
                    
                    exchange_summary["currencies"][currency] = amount
                    
                    if currency == "USDT" or currency == "USD":
                        if isinstance(exchange_summary["total_usdt"], (int, float)):
                            exchange_summary["total_usdt"] += amount
                        else:
                            exchange_summary["total_usdt"] = amount
                    elif price_usdt and price_usdt > 0:
                        if isinstance(exchange_summary["total_usdt"], (int, float)):
                            exchange_summary["total_usdt"] += amount * price_usdt
                        else:
                            exchange_summary["total_usdt"] = amount * price_usdt
                    else:
                        exchange_summary["total_usdt"] = "N/A"
            
            summary["exchanges"][exchange_name] = exchange_summary
            if exchange_summary["total_usdt"] != "N/A":
                summary["total_usdt"] += exchange_summary["total_usdt"]
            else:
                summary["total_usdt"] = "N/A"
                break  # Exit loop since we can't calculate overall total
        
        return summary

    def get_performance_aegis(self):
        try:
            performance = PerformanceAegis.query.first()
            if performance:
                return performance.serialize()
            else:
                # Create initial record if none exists
                performance = PerformanceAegis(amount=0.0)
                performance.save()
                return performance.serialize()
        except Exception as e:
            print(f"Error getting performance aegis: {e}")
            return {"id": None, "amount": 0.0, "date": None}

    def update_performance_aegis(self, amount: float):
        try:
            performance = PerformanceAegis.query.get(1)
            if performance:
                performance.amount = amount
                performance.date = datetime.utcnow()
                performance.update()
                print(f"✅ Updated PerformanceAegis (ID: 1) to amount: {amount}")
                return True
            else:
                # Create new record with ID 1 if none exists
                performance = PerformanceAegis()
                performance.id = 1
                performance.amount = amount
                performance.date = datetime.utcnow()
                performance.save()
                print(f"✅ Created new PerformanceAegis (ID: 1) with amount: {amount}")
                return True
        except Exception as e:
            print(f"❌ Error updating performance aegis: {e}")
            return False

    def add_referral_earning(self, user_id: str, referred_user_id: str, amount: float):
        try:
            from app.models.referral_earnings import add_referral_earning
            add_referral_earning(user_id, referred_user_id, amount)
            return True
        except Exception as e:
            print(f"Error adding referral earning: {e}")
            return False
