import os
import time
import pandas as pd
import requests
from datetime import datetime
from dotenv import load_dotenv
import logging

class TradingBotLegacy:
    def __init__(self, pair='XXBTZUSD', interval=5, use_heikin_ashi=False):
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('trading_bot.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        load_dotenv()
        self.PAIR = pair
        self.INTERVAL = interval
        self.USE_HEIKIN_ASHI = use_heikin_ashi
        self.API_URL = 'https://api.kraken.com'
        self.API_KEY = os.getenv('KRAKEN_API_KEY')
        self.API_SECRET = os.getenv('KRAKEN_API_SECRET')
        
        self.state = {
            "modo": "monitoreo",
            "precio_referencia": None,
            "tipo_operacion": None,
            "precio_compra": None,
            "ultima_vela_procesada": None
        }

    def get_kraken_signature(self, urlpath, data, secret):
        pass  # Implementar firma API según documentación Kraken

    def get_ohlc(self):
        self.logger.debug(f"Fetching OHLC data for {self.PAIR} with interval {self.INTERVAL}")
        url = f'{self.API_URL}/0/public/OHLC'
        params = {'pair': self.PAIR, 'interval': self.INTERVAL}
        response = requests.get(url, params=params)
        data = response.json()
        ohlc = data['result'][list(data['result'].keys())[0]]
        df = pd.DataFrame(ohlc, columns=['time', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count'])
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df[['open','high','low','close']] = df[['open','high','low','close']].astype(float)
        
        if self.USE_HEIKIN_ASHI:
            df = self.calcular_heikin_ashi(df)
        
        return df

    def calcular_heikin_ashi(self, df):
        self.logger.debug("Calculating Heikin-Ashi candles")
        ha_df = df.copy()
        ha_df['close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4

        
        for i in range(len(df)):
            if i == 0:
                ha_df.loc[i, 'open'] = (df.loc[i, 'open'] + df.loc[i, 'close']) / 2
            else:
                ha_df.loc[i, 'open'] = (ha_df.loc[i-1, 'open'] + ha_df.loc[i-1, 'close']) / 2
        
        ha_df['high'] = ha_df[['open','close','high']].max(axis=1)
        ha_df['low'] = ha_df[['open','close','low']].min(axis=1)
        
        return ha_df

    def ejecutar_orden(self, tipo, precio, cantidad):
        print("Ejecutando orden...")
        if not self.API_KEY or not self.API_SECRET:
            print("Error: Credenciales API no configuradas")
            return False
        
        self.logger.info(f"Preparing {tipo} order for {cantidad} at {precio}")
        
        urlpath = '/0/private/AddOrder'
        nonce = str(int(time.time() * 1000))
        data = {
            'nonce': nonce,
            'ordertype': 'limit',
            'type': tipo,
            'price': str(precio),
            'volume': str(cantidad),
            'pair': self.PAIR
        }
        
        signature = self.get_kraken_signature(urlpath, data, self.API_SECRET)
        headers = {
            'API-Key': self.API_KEY,
            'API-Sign': signature
        }
        
        try:
            response = requests.post(f"{self.API_URL}{urlpath}", headers=headers, data=data)
            result = response.json()
            if 'error' in result and result['error']:
                print(f"Error en la orden: {result['error']}")
                return False
            return True
        except Exception as e:
            print(f"Error al ejecutar orden: {e}")
            return False

    def detectar_patrones(self, df):
        print("Detectando patrones...")
        if len(df) < 2:
            return None
            
        ultima = df.iloc[-1]
        penultima = df.iloc[-2]

        self.logger.info(f"Analyzing candle at {ultima['time']}")
        self.logger.info(f"Open: {ultima['open']}, High: {ultima['high']}, Low: {ultima['low']}, Close: {ultima['close']}")


        if self._detectar_martillo(ultima):
            return 'martillo'
        elif self._detectar_estrella_fugaz(ultima):
            return 'estrella_fugaz'
        elif self._detectar_doji(ultima):
            return 'doji'
        elif self._detectar_envolvente_alcista(penultima, ultima):
            return 'envolvente_alcista'
        elif self._detectar_envolvente_bajista(penultima, ultima):
            return 'envolvente_bajista'
        return None

    def _detectar_martillo(self, vela):
        self.logger.info("Detecting martillo pattern")
        cuerpo = abs(vela['close'] - vela['open'])
        sombra_inferior = min(vela['open'], vela['close']) - vela['low']
        sombra_superior = vela['high'] - max(vela['open'], vela['close'])
        return sombra_inferior > 2 * cuerpo and sombra_superior < cuerpo

    def _detectar_estrella_fugaz(self, vela):
        self.logger.info("Detecting estrella fugaz pattern")
        cuerpo = abs(vela['close'] - vela['open'])
        sombra_superior = vela['high'] - max(vela['close'], vela['open'])
        sombra_inferior = min(vela['close'], vela['open']) - vela['low']
        return sombra_superior > 2 * cuerpo and sombra_inferior < cuerpo

    def _detectar_doji(self, vela):
        self.logger.info("Detecting doji pattern")
        return abs(vela['close'] - vela['open']) < ((vela['high'] - vela['low']) * 0.1)

    def _detectar_envolvente_alcista(self, prev, actual):
        self.logger.info("Detecting envolvente alcista pattern")
        return prev['close'] < prev['open'] and actual['close'] > actual['open'] and actual['close'] > prev['open'] and actual['open'] < prev['close']

    def _detectar_envolvente_bajista(self, prev, actual):
        self.logger.info("Detecting envolvente bajista pattern")
        return prev['close'] > prev['open'] and actual['close'] < actual['open'] and actual['open'] > prev['close'] and actual['close'] < prev['open']

    def _porcentaje_cambio(self, actual, referencia):
        self.logger.info("Calculating percentage change")
        return (actual - referencia) / referencia * 100

    def ejecutar_estrategia(self, df):
        if df is None or len(df) < 2:
            self.logger.warning("No valid data received for strategy execution")
            return
        
        try:
            ultima_vela = df.iloc[-1]
            
            if self.state['ultima_vela_procesada'] is not None and ultima_vela['time'] == self.state['ultima_vela_procesada']:
                self.logger.debug("Candle already processed, skipping")
                return
            
            self.logger.info(f"Processing new candle at {ultima_vela['time']}")
            self.state['ultima_vela_procesada'] = ultima_vela['time']
            
            precio_actual = ultima_vela['close']
            patron = self.detectar_patrones(df)
            
            self.logger.debug(f"Current state: {self.state}")
            self.logger.debug(f"Current price: {precio_actual}")

            if self.state['modo'] == 'monitoreo' and patron:
                self.state['precio_referencia'] = precio_actual
                if patron in ['martillo', 'envolvente_alcista', 'doji']:
                    self.state['modo'] = 'esperando_subida'
                    self.state['tipo_operacion'] = 'alza'
                    print(f"[{patron.upper()}] Detectado. Esperando subida para compra.")
                elif patron in ['estrella_fugaz', 'envolvente_bajista']:
                    self.state['modo'] = 'esperando_bajada'
                    self.state['tipo_operacion'] = 'baja'
                    print(f"[{patron.upper()}] Detectado. Esperando bajada para venta.")

            elif self.state['modo'] == 'esperando_subida' and self.state['tipo_operacion'] == 'alza':
                if self._porcentaje_cambio(precio_actual, self.state['precio_referencia']) >= 2:
                    print(f"[COMPRA] Subida confirmada (+2%). Precio: {precio_actual:.2f}")
                    self.state['precio_compra'] = precio_actual
                    self.state['modo'] = 'esperando_venta_alza'
                    self.ejecutar_orden('buy', precio_actual, 0.001)

                elif self._porcentaje_cambio(precio_actual, self.state['precio_referencia']) <= -2:
                    print(f"[CANCELAR COMPRA] Bajó -2% desde referencia. Reiniciando monitoreo.")
                    self.reset_state()

            elif self.state['modo'] == 'esperando_venta_alza':
                if self._porcentaje_cambio(precio_actual, self.state['precio_compra']) >= 3:
                    print(f"[VENTA CON GANANCIA] +3% desde compra. Precio: {precio_actual:.2f}")
                    self.ejecutar_orden('sell', precio_actual, 0.001)
                    self.reset_state()

            elif self.state['modo'] == 'esperando_bajada' and self.state['tipo_operacion'] == 'baja':
                if self._porcentaje_cambio(precio_actual, self.state['precio_referencia']) <= -2:
                    print(f"[VENTA EN BAJA] Bajada confirmada (-2%). Precio: {precio_actual:.2f}")
                    self.state['precio_compra'] = precio_actual
                    self.state['modo'] = 'esperando_recompra_baja'
                    self.ejecutar_orden('sell', precio_actual, 0.001)

            elif self.state['modo'] == 'esperando_recompra_baja':
                if self._porcentaje_cambio(precio_actual, self.state['precio_compra']) >= 2:
                    print(f"[RECOMPRA EN SUBIDA] +2% desde mínima. Precio: {precio_actual:.2f}")
                    self.state['modo'] = 'esperando_venta_alza'
                    self.ejecutar_orden('buy', precio_actual, 0.001)
                elif self._porcentaje_cambio(precio_actual, self.state['precio_compra']) <= -2:
                    print(f"[CONTINÚA BAJANDO] Bajó otro -2%. Manteniendo posición...")
        except Exception as e:
            self.logger.error(f"Error in ejecutar_estrategia: {str(e)}", exc_info=True)

    def reset_state(self):
        self.state = {
            "modo": "monitoreo",
            "precio_referencia": None,
            "tipo_operacion": None,
            "precio_compra": None,
            "ultima_vela_procesada": None
        }

    def run(self):
        self.logger.info("Starting JapaneseCandleBot")
        self.logger.info(f"Configuration: Pair={self.PAIR}, Interval={self.INTERVAL}min, Heikin-Ashi={self.USE_HEIKIN_ASHI}")
        
        while True:
            try:
                self.logger.debug("Starting new iteration")
                df = self.get_ohlc()
                if df is not None:
                    self.ejecutar_estrategia(df)
                else:
                    self.logger.warning("Received empty DataFrame, skipping strategy execution")
                
                sleep_time = self.INTERVAL * 60
                self.logger.debug(f"Sleeping for {sleep_time} seconds")
                time.sleep(sleep_time)
                
            except KeyboardInterrupt:
                self.logger.info("Bot stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in main loop: {str(e)}", exc_info=True)
                time.sleep(60)  # Wait before retrying after error

if __name__ == "__main__":
    bot = TradingBotLegacy()
    bot.run()