# CODIGO Q SE USO PARA ENTRENAR EL MODELO

import ccxt
import pandas as pd
import os
import time
from dotenv import load_dotenv

# Cargar credenciales desde archivo .env
load_dotenv()

# Configurar conexión con Kraken
api_key = os.getenv("KRAKEN_API_KEY")
api_secret = os.getenv("KRAKEN_API_SECRET")

exchange = ccxt.kraken({
    'apiKey': api_key,
    'secret': api_secret
})

# Parámetros del mercado
symbol = 'XXBTZUSD'  # Kraken usa XXBTZUSD para BTC/USD
timeframe = '1h'     # Usamos 1 hora para agrupar en 2 horas
limit = 500          # Máximo permitido por Kraken

# Verificar conexión con Kraken
try:
    print(f"Probando conexión con Kraken y verificando símbolo: {symbol}")
    ticker = exchange.fetch_ticker(symbol)
    print(f"✅ Conexión exitosa. Precio actual de {symbol}: {ticker['last']}")
except Exception as e:
    print(f"❌ Error al conectar con Kraken: {e}")
    exit()

# Function to determine trading signals
def check_buy_sell_signals(df, i):
    buy_signal = False
    sell_signal = False
    
    # EMA crossover strategy
    if df['EMA12'].iloc[i] > df['EMA26'].iloc[i] and df['EMA12'].iloc[i-1] <= df['EMA26'].iloc[i-1]:
        buy_signal = True
    elif df['EMA12'].iloc[i] < df['EMA26'].iloc[i] and df['EMA12'].iloc[i-1] >= df['EMA26'].iloc[i-1]:
        sell_signal = True
    
    # RSI strategy
    if df['RSI'].iloc[i] < 30:
        buy_signal = True
    elif df['RSI'].iloc[i] > 70:
        sell_signal = True
        
    return buy_signal, sell_signal

# Función para calcular indicadores
def calculate_indicators(df):
    # Resampling para asegurar que los datos estén en el marco de tiempo de 2 horas
    df = df.set_index('timestamp').resample('2h').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()

    # Cálculo de la EMA de 50
    df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()

    # Cálculo de la EMA de 12 y 26
    df['EMA12'] = df['close'].ewm(span=12, adjust=False).mean()  # EMA de corto plazo
    df['EMA26'] = df['close'].ewm(span=26, adjust=False).mean()  # EMA de largo plazo

    # Cálculo del MACD
    df['MACD'] = df['EMA12'] - df['EMA26']  # MACD = EMA12 - EMA26
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()  # Signal = EMA9(MACD)

    # Cálculo del RSI (14 períodos)
    delta = df['close'].diff()  # Cambios diarios
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()  # Ganancia media
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()  # Pérdida media
    rs = gain / loss  # Relación de fuerza
    df['RSI'] = 100 - (100 / (1 + rs))  # RSI

    # Detección de patrones de velas
    df['doji'] = abs(df['close'] - df['open']) / (df['high'] - df['low']) < 0.1
    df['hammer'] = (df['close'] - df['open']).abs() < (df['high'] - df['low']) * 0.3
    df['hammer'] &= (df['low'] - df['open']) > (df['high'] - df['close'])
    df['bullish_engulfing'] = (df['close'] > df['open']) & (df['open'].shift(1) > df['close'].shift(1)) & (df['close'] > df['open'].shift(1)) & (df['open'] < df['close'].shift(1))
    df['bearish_engulfing'] = (df['close'] < df['open']) & (df['open'].shift(1) < df['close'].shift(1)) & (df['close'] < df['open'].shift(1)) & (df['open'] > df['close'].shift(1))
    df['shooting_star'] = (df['close'] - df['open']).abs() < (df['high'] - df['low']) * 0.3
    df['shooting_star'] &= (df['high'] - df['close']) > (df['close'] - df['open'])
    df['morning_star'] = (df['close'].shift(2) < df['open'].shift(2)) & (df['open'].shift(1) < df['close'].shift(1)) & (df['close'] > df['open'])
    df['evening_star'] = (df['close'].shift(2) > df['open'].shift(2)) & (df['open'].shift(1) > df['close'].shift(1)) & (df['close'] < df['open'])

    # Asegurarse de que no haya valores NaN
    return df.dropna()

# Función para guardar la Q-table
def save_q_table():
    q_table.to_csv("q_table.csv", index=False)

# Cargar tabla Q desde archivo (si existe)
if os.path.exists("q_table.csv"):
    q_table = pd.read_csv("q_table.csv")
else:
    q_table = pd.DataFrame()

# Función para imprimir balance y estadísticas
def print_balance():
    global total_profit, operation_count, balance
    if operation_count > 0:
        profit_percentage = (total_profit / (balance + total_profit)) * 100
    else:
        profit_percentage = 0

    print(f"\n📊 Balance: {balance:.2f} USD")
    print(f"🔄 Total de operaciones: {operation_count}")
    print(f"💰 Ganancia total: {total_profit:.2f} USD")
    print(f"📈 Porcentaje de ganancia: {profit_percentage:.2f}%")
    print(f"✅ Operaciones exitosas: {operation_count}")  # Agregado
    print(f"⚖️ Balance total: {balance + total_profit:.2f} USD")  # Agregado

# Variables para el seguimiento del balance y operaciones
balance = 1000  # Ejemplo de saldo inicial
total_profit = 0
operation_count = 0
position = None
entry_price = 0

# Bucle principal para operar en tiempo real
start_time = time.time()
while True:
    try:
        print(f"⌛️ Esperando a la siguiente iteración...")
        # Obtener datos de mercado en tiempo real
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # Calcular indicadores
        df = calculate_indicators(df)

        # Short df to 2 rows
        df = df[-2:]

        # Estrategia 1: Basada en Indicadores Principales
        for i in range(1, len(df)):
            try:
                print(f"🚀 Iteración {i} de {len(df)}")
                price = df['close'].iloc[i]

                # Detectar variaciones significativas en los indicadores
                buy_signal, sell_signal = check_buy_sell_signals(df, i)

                # Condiciones para realizar la compra o venta
                if position is None and buy_signal:
                    position, entry_price = 'BUY', price
                    amount_to_buy = balance / price
                    balance -= amount_to_buy * price
                    operation_count += 1

                elif position == 'BUY' and sell_signal:
                    balance += price  # Simular la venta
                    position = None
                    profit = price - entry_price
                    total_profit += profit
                    operation_count += 1

                # Estrategia 2: Patrones de Velas y Soporte/Resistencia
                if position is None and not buy_signal and not sell_signal:
                    if df.iloc[i]['doji'] or df.iloc[i]['hammer'] or df.iloc[i]['morning_star']:
                        position, entry_price = 'BUY', price
                        amount_to_buy = balance / price
                        balance -= amount_to_buy * price
                        operation_count += 1

                    elif df.iloc[i]['shooting_star'] or df.iloc[i]['bearish_engulfing'] or df.iloc[i]['evening_star']:
                        balance += price  # Simular la venta
                        position = None
                        profit = price - entry_price
                        total_profit += profit
                        operation_count += 1

                # Estrategia 3: Monitoreo de Variaciones y Patrones de Velas
                if position is None:
                    if price > entry_price * 1.002:  # Subida de 0.2%
                        position, entry_price = 'BUY', price
                        amount_to_buy = balance / price
                        balance -= amount_to_buy * price
                        operation_count += 1
                    elif price < entry_price * 0.998:  # Bajada de 0.2%
                        balance += price
                        position = None
                        profit = entry_price - price
                        total_profit += profit
                        operation_count += 1

                # Re-evaluar la operación si hay una variación importante en los precios
                if position == 'BUY':
                    if price >= entry_price * 1.003:  # Subida de 0.3% después de compra
                        balance += price  # Simular la venta
                        position = None
                        profit = price - entry_price
                        total_profit += profit
                        operation_count += 1

                # Guardar la tabla Q cada vez
                save_q_table()

            except Exception as e:
                print(f"❌ Error en el ciclo (índice {i}): {str(e)}")
                time.sleep(10)  # Espera antes de intentar nuevamente

        # Imprimir balance y estadísticas cada 5 minutos
        if time.time() - start_time >= 300:  # 300 segundos = 5 minutos
            print_balance()
            start_time = time.time()

        time.sleep(60)  # Espera antes de la siguiente iteración

    except Exception as e:
        print(f"❌ Error general: {str(e)}")
        time.sleep(10)  # Espera antes de intentar nuevamente
