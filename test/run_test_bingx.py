import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.viewmodels.api.exchange.Exchange import ExchangeFactory
from app.Aplicacion import Application
from app.config import config

import ccxt

app_instance = Application(config)

symbol = "BTC/USDT:USDT"
amount = 0.0001

def test_bingx_future_buy():
    with app_instance.app_context():
        # Crea una instancia del exchange BingX Future
        exchange = ExchangeFactory.create_exchange(name='bingx', trading_mode="swap")

        buy_order = exchange.add_order(
            order_direction="buy",
            symbol=symbol,
            volume=amount,
            order_type="market",
            order_made_by="bot"
        )

        print(buy_order)

def test_bingx_future_sell():
    with app_instance.app_context():
        # Crea una instancia del exchange BingX Future
        exchange = ExchangeFactory.create_exchange(name='bingx', trading_mode="swap")

        sell_order = exchange.add_order(
            order_direction="sell",
            symbol=symbol,
            volume=amount,
            order_type="market",
            order_made_by="bot"
        )

        print(sell_order)

def test_bingx_future_positions():
    exchange = ccxt.bingx(
        {
            "apiKey": config.BINGX_API_KEY_FUTURES,
            "secret": config.BINGX_API_SECRET_FUTURES,
            "options": {
                "defaultType": "swap",
            },
            "enableRateLimit": True,
        }
    )

    open_positions = exchange.fetch_positions()

    for pos in open_positions:
        pos_symbol = pos.get('symbol')
        pos_side = pos.get('side')  # 'long' o 'short'
        contracts = pos.get('contracts')

        print(f"Symbol: {pos_symbol}, Side: {pos_side}, Contracts: {contracts}")

def close_all_bingx_future_positions():
    exchange = ccxt.bingx({
        "apiKey": config.BINGX_API_KEY_FUTURES,
        "secret": config.BINGX_API_SECRET_FUTURES,
        "options": {"defaultType": "swap"},
        "enableRateLimit": True,
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

##########################################################

def tests():    
    while True:
        print("--------------------------------")
        print("¿Qué acción quieres realizar?")
        print("1. Ver posiciones abiertas")
        print("2. Cerrar todas las posiciones")
        print("3. Comprar")
        print("4. Vender")
        print("0. Salir")
        print("--------------------------------")

        try:
            choice = input("\nIngresa tu elección: ").strip()
            
            if choice == "1":
                print("\n=== Verificando posiciones abiertas ===")
                test_bingx_future_positions()
            elif choice == "2":
                print("\n=== Cerrando todas las posiciones ===")
                confirm = input("¿Estás seguro de que quieres cerrar todas las posiciones? (s/n): ").strip().lower()
                if confirm in ['s', 'si', 'sí', 'y', 'yes']:
                    close_all_bingx_future_positions()
                else:
                    print("Cancelado")
            elif choice == "3":
                print("\n=== Comprando y vendiendo ===")
                test_bingx_future_buy()
            elif choice == "4":
                print("\n=== Venta ===")
                test_bingx_future_sell()
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