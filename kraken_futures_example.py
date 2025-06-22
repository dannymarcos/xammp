import ccxt
import argparse

# --- CONFIGURACIÓN DE API (NO compartas tus claves en público) ---
API_KEY = '1kWBgDCKap5OtPVWw0Yn5x3rseXrnyb0NZA0f3tgVEVo8FFcavqySGUN'
API_SECRET = 'rDzCkSp+EVq1s03IvemM1GI//itRXO5OsH5IYedIKzijjs9FJp69AooBFXMN2ZI4OyO+7tGe1kWm4B+NxJnnhm/J'

# --- CONFIGURACIÓN DE EXCHANGE ---
exchange = ccxt.krakenfutures({
    'apiKey': API_KEY,
    'secret': API_SECRET,
})
symbol = "RENDER/USD:USD"
min_amount = 1
try:
    # --- MOSTRAR SALDO DISPONIBLE ---
    print('Obteniendo saldo disponible en Kraken Futures...')
    balance = exchange.fetch_balance()
    print('Saldo disponible:')
    for currency, info in balance['total'].items():
        print(f"{currency}: {info}")

    # --- OBTENER INFORMACIÓN DEL MERCADO PARA EL MÍNIMO ---
    print('\nObteniendo información del mercado para determinar el monto mínimo...')
    markets = exchange.load_markets()
    if symbol not in markets:
        # print symbols
        print("Mercados disponibles:")
        for market in markets:
            print(market)
        raise Exception(f"El símbolo {symbol} no se encontró en los mercados disponibles.")
    market = markets[symbol]
    # min_amount = market['limits']['amount']['min']
    contract_size = market.get('contractSize', 1)
    print(f"Monto mínimo permitido para {symbol}: {min_amount} contratos")
    print(f"Multiplicador del contrato (USD por contrato): {contract_size}")

    # --- OBTENER PRECIO ACTUAL ---
    ticker = exchange.fetch_ticker(symbol)
    mark_price = ticker['last']
    print(f"Precio actual de {symbol}: {mark_price}")

    # --- CALCULAR TAMAÑO MÍNIMO DE ORDEN ---
    min_contracts = min_amount * contract_size if contract_size < 1 else min_amount
    min_usd = min_contracts * mark_price
    print(f"Tamaño mínimo de orden: {min_contracts} contratos (~{min_usd:.2f} USD)")

    # --- ESTIMAR MARGEN REQUERIDO ---
    leverage = 2
    required_margin = min_usd / leverage
    print(f"Margen requerido estimado para {symbol} con apalancamiento {leverage}x: ~{required_margin:.2f} USD")

    # --- VERIFICAR POSICIONES ABIERTAS ---
    print('\nConsultando posiciones abiertas...')
    open_positions = []
    if hasattr(exchange, 'fetch_positions'):
        all_positions = exchange.fetch_positions()
        print(f"Posiciones abiertas encontradas: {len(all_positions)}")
        for pos in all_positions:
            pos_symbol = pos.get('symbol') or pos.get('info', {}).get('symbol')
            contracts = pos.get('contracts') or pos.get('info', {}).get('size')
            contracts_float = 0.0
            if contracts is not None:
                try:
                    contracts_float = float(contracts)
                except (TypeError, ValueError):
                    contracts_float = 0.0
            if pos_symbol == symbol and abs(contracts_float) > 0:
                open_positions.append(pos)
    else:
        print("Este exchange no soporta fetch_positions() en ccxt. Consulta tus posiciones manualmente en Kraken.")

    if open_positions:
        print('Ya tienes una posición abierta en este mercado:')
        for pos in open_positions:
            print(pos)
        print('No se abrirá una nueva posición para evitar el error maxPositionViolation.')
    else:
        # --- VERIFICAR SI HAY SUFICIENTE SALDO ---
        available_usd = balance['total'].get('USD', 0)
        print(f"Saldo USD disponible: {available_usd}")

        if available_usd < required_margin:
            print(f"Advertencia: Tu saldo disponible ({available_usd} USD) es menor al margen requerido estimado ({required_margin:.2f} USD) para abrir la posición mínima con apalancamiento {leverage}x.")
            print("No se intentará abrir la posición para evitar el error maxPositionViolation.")
        else:
            # --- ABRIR POSICIÓN CON EL MÍNIMO PERMITIDO ---
            print(f'\nAbriendo posición LONG en {symbol} por {min_amount} contratos...')
            order = exchange.create_market_buy_order("RENDER/USD:USD", 1)
            print('Posición LONG abierta:')
            print(order)

            # --- CERRAR POSICIÓN ---
            print(f'\nCerrando posición en {symbol} por {min_amount} contratos...')
            close_order = exchange.create_market_sell_order(symbol, min_amount)
            print('Posición cerrada:')
            print(close_order)

except Exception as e:
    print('Error al operar con Kraken Futures:', e)

# --- USAGE ---
# python kraken_futures_example.py --symbol SYMBOL (e.g. BTC/USD:USD)
