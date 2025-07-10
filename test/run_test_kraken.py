import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.viewmodels.api.exchange.Exchange import ExchangeFactory
from app.Aplicacion import Application
from app.config import config

import ccxt

app_instance = Application(config)
symbol = "PYTH/USD:USD"  # Bitcoin futures symbol for Kraken
volume = 5  # Small amount for testing

def test_kraken_future_buy():
    with app_instance.app_context():
        # Crea una instancia del exchange Kraken Future
        exchange = ExchangeFactory.create_exchange(name='kraken_future')

        buy_order = exchange.add_order(
            order_type="market",
            order_direction="buy",
            volume=volume,
            symbol=symbol,
            leverage=1,
            take_profit=None,
            stop_loss=None,
            order_made_by="user"
        )

        print(buy_order)

def test_kraken_future_sell():
    with app_instance.app_context():
        # Crea una instancia del exchange Kraken Future
        exchange = ExchangeFactory.create_exchange(name='kraken_future')

        sell_order = exchange.add_order(
            order_type="market",
            order_direction="sell",
            volume=volume,
            symbol=symbol,
            leverage=1,
            order_made_by="bot"
        )

        print(sell_order)

def test_kraken_future_positions():
    # Using ccxt directly for position checking
    exchange = ccxt.krakenfutures({
        'apiKey': config.KRAKEN_FUTURE_API_KEY,
        'secret': config.KRAKEN_FUTURE_API_SECRET,
        'enableRateLimit': True,
    })

    try:
        open_positions = exchange.fetch_positions()

        for pos in open_positions:
            pos_symbol = pos.get('symbol')
            pos_side = pos.get('side')  # 'long' o 'short'
            contracts = pos.get('contracts')
            notional = pos.get('notional')

            if contracts and float(contracts) != 0:
                print(f"Symbol: {pos_symbol}, Side: {pos_side}, Contracts: {contracts}, Notional: {notional}")
    except Exception as e:
        print(f"Error fetching positions: {e}")

def test_kraken_future_balance():
    with app_instance.app_context():
        exchange = ExchangeFactory.create_exchange(name='kraken_future')
        
        balance = exchange.get_account_balance()
        print("Account Balance:")
        print(balance)

def test_kraken_future_symbol_price():
    with app_instance.app_context():
        exchange = ExchangeFactory.create_exchange(name='kraken_future')

        price, error = exchange.get_symbol_price(symbol)
        
        if error:
            print(f"Error getting price: {error}")
        else:
            print(f"Current price for {symbol}: {price}")

def close_all_kraken_future_positions():
    exchange = ccxt.krakenfutures({
        'apiKey': config.KRAKEN_FUTURE_API_KEY,
        'secret': config.KRAKEN_FUTURE_API_SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'swap',  # Para futuros
        }
    })
    
    # 1. Obtener todas las posiciones abiertas
    open_positions = exchange.fetch_positions()
    
    for pos in open_positions:
        pos_symbol = pos['symbol']
        contracts = float(pos['contracts'])
        
        # Saltar si no hay posición abierta
        if contracts <= 0:
            continue
            
        # 2. Determinar dirección para cerrar
        side_to_close = 'sell' if pos['side'] == 'long' else 'buy'
        
        try:
            # 3. Crear orden de mercado para cerrar
            order = exchange.create_order(
                symbol=pos_symbol,
                type='market',
                side=side_to_close,
                amount=contracts,
                params={
                    "reduce_only": True,  # Solo reduce posición existente
                    "positionSide": pos['side'].upper()  # Especificar LONG/SHORT
                }
            )
            print(f"✅ Cerrada posición {pos['side']} de {contracts} contratos en {pos_symbol}")
            print(f"Detalles orden: {order['id']} @ {order['price']}")
            
        except Exception as e:
            print(f"❌ Error cerrando {pos_symbol}: {e}")

# exchange = ccxt.krakenfutures({
#     'apiKey': config.KRAKEN_FUTURE_API_KEY,
#     'secret': config.KRAKEN_FUTURE_API_SECRET,
#     'enableRateLimit': True,
#     'options': {
#         'defaultType': 'swap',  # Para futuros
#     }
# })

# markets = exchange.load_markets()

# pyth_symbol = None

# # Buscar el símbolo correcto para PYTH
# for symbol in markets:
#     if 'PYTH' in symbol and '/USD' in symbol:
#         pyth_symbol = symbol
#         break

# if not pyth_symbol:
#     raise Exception("❌ PYTH no encontrado en Kraken Futures. Verifica los símbolos disponibles.")

# print(f"✅ Símbolo encontrado: {pyth_symbol}")

def tests():    
    while True:
        print("--------------------------------")
        print("¿Qué acción quieres realizar?")
        print("1. Ver posiciones abiertas")
        print("2. Cerrar todas las posiciones")
        print("3. Comprar")
        print("4. Vender")
        print("5. Balance")
        print("0. Salir")
        print("--------------------------------")

        try:
            choice = input("\nIngresa tu elección: ").strip()
            
            if choice == "1":
                print("\n=== Verificando posiciones abiertas ===")
                test_kraken_future_positions()
            elif choice == "2":
                print("\n=== Cerrando todas las posiciones ===")
                confirm = input("¿Estás seguro de que quieres cerrar todas las posiciones? (s/n): ").strip().lower()
                if confirm in ['s', 'si', 'sí', 'y', 'yes']:
                    close_all_kraken_future_positions()
                else:
                    print("Cancelado")
            elif choice == "3":
                print("\n=== Comprando ===")
                test_kraken_future_buy()
            elif choice == "4":
                print("\n=== Venta ===")
                test_kraken_future_sell()
            elif choice == "5":
                print("\n=== Balance ===")
                test_kraken_future_balance()
            elif choice == "0":
                print("Saliendo...")
                break
            else:
                print("Opción no válida. Por favor ingresa 1, 2 o 3.")
                
        except KeyboardInterrupt:
            print("\n\nOperación cancelada por el usuario.")
            break
        except Exception as e:
            print(f"Error: {e}")

tests()