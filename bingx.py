import ccxt
import json

# --- API CONFIGURATION (Do not share your keys publicly) ---
API_KEY = 'PbyEvuaUD9ShIIuaiB4FTsZDOLgiBeUNEZWnkgaZ8aIidEqN98ESsL2G9k7H5TVjtrbnVwOjbZLhBgKJrbg'
API_SECRET = 'fFahVhTrozw7TQJVzf0EpP02zIpP1eBFgMnVFCMElp210RCDZsdTxHiqW2QZ29AA5e34BfCtM55DiIxsAnQ'

def trade_spot():
    print("\n=== BingX SPOT Trading ===")
    exchange = ccxt.bingx({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'options': {
            'defaultType': 'spot',
        }
    })
    symbol = "BTC/USDT:USDT"
    min_amount = 0.0001  # Will fetch actual from market info

    try:
        print('Fetching available balance on BingX Spot...')
        balance = exchange.fetch_balance()
        print('Available balance:')
        for currency, info in balance['total'].items():
            print(f"{currency}: {info}")

        print('\nFetching market info to determine minimum amount...')
        markets = exchange.load_markets()
        if symbol not in markets:
            print("Available markets:")
            for market in markets:
                print(market)
            raise Exception(f"Symbol {symbol} not found in available markets.")
        market = markets[symbol]
        min_amount = market['limits']['amount']['min'] if market['limits']['amount']['min'] else min_amount
        print(f"Minimum allowed amount for {symbol}: {min_amount}")

        print('\nFetching open trades...')
        open_trades = exchange.fetch_open_orders(symbol)
        print('Open trades:')
        for trade in open_trades:
            print(trade)

        print('\nFetching history trades...')
        history_trades = exchange.fetch_closed_orders(symbol)
        print('History trades:')
        print(len(history_trades))

        ticker = exchange.fetch_ticker(symbol)
        last_price = ticker['last']
        print(f"Current price of {symbol}: {last_price}")

        min_usd = min_amount * last_price
        print(f"Minimum order size: {min_amount} {symbol.split('/')[0]} (~{min_usd:.2f} USDT)")

        quote_currency = symbol.split('/')[1]
        available_quote = balance['total'].get("USDT", 0)
        print(f"Available {quote_currency} balance: {available_quote}")

        
        print(f'\nPlacing market BUY order for {min_amount} {symbol.split("/")[0]}...')
        #order = exchange.create_market_buy_order(symbol, min_amount)
        #print('Buy order placed:')
        # print(order)

        print(f'\nPlacing market SELL order for {min_amount} {symbol.split("/")[0]}...')
        sell_order = exchange.create_market_sell_order(symbol, min_amount, params={"positionSide": "SHORT"})
        print('Sell order placed:')
        print(sell_order)

    except Exception as e:
        print('Error operating with BingX Spot:', e)

def trade_futures():
    print("\n=== BingX FUTURES Trading ===")
    exchange = ccxt.bingx({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'options': {
            'defaultType': 'swap',  # 'swap' is used for USDT-margined futures in ccxt
        }
    })
    symbol = "BTC/USDT:USDT"
    min_amount = 0.001  # Will fetch actual from market info

    try:
        print('Fetching available balance on BingX Futures...')
        balance = exchange.fetch_balance()
        print('Available balance:')
        for currency, info in balance['total'].items():
            print(f"{currency}: {info}")

        print('\nFetching market info to determine minimum amount...')
        markets = exchange.load_markets()
        if symbol not in markets:
            print("Available markets:")
            for market in markets:
                print(market)
            raise Exception(f"Symbol {symbol} not found in available markets.")
        market = markets[symbol]
        min_amount = market['limits']['amount']['min']
        print(f"Minimum allowed amount for {symbol}: {min_amount}")

        print('\nFetching open trades...')
        open_trades = exchange.fetch_open_orders(symbol)
        print('Open trades:')
        for trade in open_trades:
            print(trade)

        print('\nFetching history trades...')
        history_trades = exchange.fetch_closed_orders(symbol)
        print('History trades:')
        print(len(history_trades))

        ticker = exchange.fetch_ticker(symbol)
        last_price = ticker['last']
        print(f"Current price of {symbol}: {last_price}")

        min_usd = min_amount * last_price
        print(f"Minimum order size: {min_amount} {symbol.split('/')[0]} (~{min_usd:.2f} USDT)")

        quote_currency = "USDT"
        available_quote = balance['total'].get(quote_currency, 0)
        print(f"Available {quote_currency} balance: {available_quote}")

        if available_quote < min_usd:
            print(f"Warning: Your available {quote_currency} balance ({available_quote}) is less than the minimum required ({min_usd:.2f}) to buy {min_amount} {symbol.split('/')[0]}.")
            print("No buy order will be placed.")
        else:
            print(f'\nPlacing market BUY order for {min_amount} {symbol.split("/")[0]}...')
            # For futures, you may need to specify positionSide
            order = exchange.create_market_buy_order(symbol, min_amount, params={"positionSide": "LONG"})
            print('Buy order placed:')
            import json
            print(json.dumps(order, indent=4))

            balance = exchange.fetch_balance()
            print('Available balance:')
            for currency, info in balance['total'].items():
                print(f"{currency}: {info}")

            print(f'\nPlacing market SELL order for {min_amount} {symbol.split("/")[0]}...')
            sell_order = exchange.create_market_sell_order(symbol, min_amount, params={"positionSide": "SHORT"})
            print('Sell order placed:')
            print(sell_order)

    except Exception as e:
        print('Error operating with BingX Futures:', e)

if __name__ == "__main__":
    # Call both for demonstration; comment out as needed
    trade_spot()
    #trade_futures()