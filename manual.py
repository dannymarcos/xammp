import os
import time
import pandas as pd
import requests
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# === CONFIGURACIÓN ===
PAIR = 'XXBTZUSD'  # Par BTC/USD
INTERVAL = 5  # Velas de 5 minutos
API_URL = 'https://api.kraken.com'
USE_HEIKIN_ASHI = False  # Cambiar a True para usar velas Heikin-Ashi

# Configuración API Kraken
API_KEY = os.getenv('KRAKEN_API_KEY')
API_SECRET = os.getenv('KRAKEN_API_SECRET')

# Estado del bot
state = {
    "modo": "monitoreo",
    "precio_referencia": None,
    "tipo_operacion": None,
    "precio_compra": None,
    "ultima_vela_procesada": None
}

# === FUNCIONES DE CONEXIÓN ===
def get_kraken_signature(urlpath, data, secret):
    pass  # Implementar firma API según documentación Kraken

def get_ohlc(pair=PAIR, interval=INTERVAL):
    url = f'{API_URL}/0/public/OHLC'
    params = {'pair': pair, 'interval': interval}
    response = requests.get(url, params=params)
    data = response.json()
    ohlc = data['result'][list(data['result'].keys())[0]]
    df = pd.DataFrame(ohlc, columns=['time', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count'])
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df[['open','high','low','close']] = df[['open','high','low','close']].astype(float)
    
    if USE_HEIKIN_ASHI:
        df = calcular_heikin_ashi(df)
    
    return df

def calcular_heikin_ashi(df):
    ha_df = df.copy()
    
    # Calcular Heikin-Ashi
    ha_df['close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    
    for i in range(len(df)):
        if i == 0:
            ha_df.loc[i, 'open'] = (df.loc[i, 'open'] + df.loc[i, 'close']) / 2
        else:
            ha_df.loc[i, 'open'] = (ha_df.loc[i-1, 'open'] + ha_df.loc[i-1, 'close']) / 2
    
    ha_df['high'] = ha_df[['open','close','high']].max(axis=1)
    ha_df['low'] = ha_df[['open','close','low']].min(axis=1)
    
    return ha_df

# === FUNCIONES DE TRADING ===
def ejecutar_orden(tipo, precio, cantidad):
    """Ejecuta una orden en Kraken"""
    if not API_KEY or not API_SECRET:
        print("Error: Credenciales API no configuradas")
        return False
    
    urlpath = '/0/private/AddOrder'
    nonce = str(int(time.time() * 1000))
    data = {
        'nonce': nonce,
        'ordertype': 'limit',
        'type': tipo,
        'price': str(precio),
        'volume': str(cantidad),
        'pair': PAIR
    }
    
    signature = get_kraken_signature(urlpath, data, API_SECRET)
    headers = {
        'API-Key': API_KEY,
        'API-Sign': signature
    }
    
    try:
        response = requests.post(f"{API_URL}{urlpath}", headers=headers, data=data)
        result = response.json()
        if 'error' in result and result['error']:
            print(f"Error en la orden: {result['error']}")
            return False
        return True
    except Exception as e:
        print(f"Error al ejecutar orden: {e}")
        return False

# === DETECCIÓN DE PATRONES ===
def detectar_martillo(vela):
    cuerpo = abs(vela['close'] - vela['open'])
    sombra_inferior = min(vela['open'], vela['close']) - vela['low']
    sombra_superior = vela['high'] - max(vela['open'], vela['close'])
    return sombra_inferior > 2 * cuerpo and sombra_superior < cuerpo

def detectar_estrella_fugaz(vela):
    cuerpo = abs(vela['close'] - vela['open'])
    sombra_superior = vela['high'] - max(vela['close'], vela['open'])
    sombra_inferior = min(vela['close'], vela['open']) - vela['low']
    return sombra_superior > 2 * cuerpo and sombra_inferior < cuerpo

def detectar_doji(vela):
    return abs(vela['close'] - vela['open']) < ((vela['high'] - vela['low']) * 0.1)

def detectar_envolvente_alcista(prev, actual):
    return prev['close'] < prev['open'] and actual['close'] > actual['open'] and actual['close'] > prev['open'] and actual['open'] < prev['close']

def detectar_envolvente_bajista(prev, actual):
    return prev['close'] > prev['open'] and actual['close'] < actual['open'] and actual['open'] > prev['close'] and actual['close'] < prev['open']

def detectar_patron(df):
    if len(df) < 2:
        return None
        
    ultima = df.iloc[-1]
    penultima = df.iloc[-2]

    if detectar_martillo(ultima):
        return 'martillo'
    elif detectar_estrella_fugaz(ultima):
        return 'estrella_fugaz'
    elif detectar_doji(ultima):
        return 'doji'
    elif detectar_envolvente_alcista(penultima, ultima):
        return 'envolvente_alcista'
    elif detectar_envolvente_bajista(penultima, ultima):
        return 'envolvente_bajista'
    return None

# === ESTRATEGIA PRINCIPAL ===
def porcentaje_cambio(actual, referencia):
    return (actual - referencia) / referencia * 100

def ejecutar_estrategia(df):
    global state
    
    if len(df) < 2:
        return
    
    ultima_vela = df.iloc[-1]
    if state['ultima_vela_procesada'] is not None and ultima_vela['time'] == state['ultima_vela_procesada']:
        return
    
    state['ultima_vela_procesada'] = ultima_vela['time']
    
    precio_actual = ultima_vela['close']
    patron = detectar_patron(df)

    if state['modo'] == 'monitoreo' and patron:
        state['precio_referencia'] = precio_actual
        if patron in ['martillo', 'envolvente_alcista', 'doji']:
            state['modo'] = 'esperando_subida'
            state['tipo_operacion'] = 'alza'
            print(f"[{patron.upper()}] Detectado. Esperando subida para compra.")
        elif patron in ['estrella_fugaz', 'envolvente_bajista']:
            state['modo'] = 'esperando_bajada'
            state['tipo_operacion'] = 'baja'
            print(f"[{patron.upper()}] Detectado. Esperando bajada para venta.")

    elif state['modo'] == 'esperando_subida' and state['tipo_operacion'] == 'alza':
        if porcentaje_cambio(precio_actual, state['precio_referencia']) >= 2:
            print(f"[COMPRA] Subida confirmada (+2%). Precio: {precio_actual:.2f}")
            state['precio_compra'] = precio_actual
            state['modo'] = 'esperando_venta_alza'
            # Ejecutar orden de compra en real
            ejecutar_orden('buy', precio_actual, 0.001)  # Ajustar cantidad según necesidad

        elif porcentaje_cambio(precio_actual, state['precio_referencia']) <= -2:
            print(f"[CANCELAR COMPRA] Bajó -2% desde referencia. Reiniciando monitoreo.")
            state = {"modo": "monitoreo", "precio_referencia": None, "tipo_operacion": None, "precio_compra": None, "ultima_vela_procesada": None}

    elif state['modo'] == 'esperando_venta_alza':
        if porcentaje_cambio(precio_actual, state['precio_compra']) >= 3:
            print(f"[VENTA CON GANANCIA] +3% desde compra. Precio: {precio_actual:.2f}")
            # Ejecutar orden de venta en real
            ejecutar_orden('sell', precio_actual, 0.001)  # Ajustar cantidad según necesidad
            state = {"modo": "monitoreo", "precio_referencia": None, "tipo_operacion": None, "precio_compra": None, "ultima_vela_procesada": None}

    elif state['modo'] == 'esperando_bajada' and state['tipo_operacion'] == 'baja':
        if porcentaje_cambio(precio_actual, state['precio_referencia']) <= -2:
            print(f"[VENTA EN BAJA] Bajada confirmada (-2%). Precio: {precio_actual:.2f}")
            state['precio_compra'] = precio_actual
            state['modo'] = 'esperando_recompra_baja'
            # Ejecutar orden de venta en corto (si el exchange lo permite)
            ejecutar_orden('sell', precio_actual, 0.001)  # Ajustar según necesidad

    elif state['modo'] == 'esperando_recompra_baja':
        if porcentaje_cambio(precio_actual, state['precio_compra']) >= 2:
            print(f"[RECOMPRA EN SUBIDA] +2% desde mínima. Precio: {precio_actual:.2f}")
            state['modo'] = 'esperando_venta_alza'
            # Ejecutar orden de compra para cerrar corto
            ejecutar_orden('buy', precio_actual, 0.001)  # Ajustar según necesidad
        elif porcentaje_cambio(precio_actual, state['precio_compra']) <= -2:
            print(f"[CONTINÚA BAJANDO] Bajó otro -2%. Manteniendo posición...")

# === LOOP PRINCIPAL ===
def run_bot():
    print("Bot de velas japonesas iniciado en Kraken.")
    print(f"Configuración actual: {'Heikin-Ashi' if USE_HEIKIN_ASHI else 'Velas tradicionales'}")
    
    while True:
        try:
            df = get_ohlc()
            ejecutar_estrategia(df)
        except Exception as e:
            print(f"[ERROR] {e}")
        time.sleep(INTERVAL * 60)

if _name_ == "_main_":
    run_bot()