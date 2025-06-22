
---

📄 **`docs/integracion_ia_kraken.md`**

# 🤖 Integración de Modelo de IA con Kraken vía LoRA

Este documento describe la arquitectura de un sistema que conecta un modelo de lenguaje personalizado con un entorno de ejecución LoRA, el cual permite ejecutar estrategias de trading automatizadas en Kraken (mercado Spot o Futuros) a través de una interfaz conversacional.

---

## 1. 🧠 Descripción General

El sistema permite que un usuario interactúe mediante un chat con un modelo de lenguaje personalizado entrenado en estrategias de trading. La IA interpreta la intención del usuario, genera una estrategia y la ejecuta automáticamente mediante:

- Un módulo LoRA (Low-Rank Adaptation)
- Conexión con la API de Kraken
- Monitoreo en tiempo real del mercado

---

## 2. 🧩 Componentes del Sistema

- **Interfaz de Chat**: punto de interacción entre el usuario y la IA.
- **Modelos de IA**: cargados desde pesos personalizados entrenados.
- **Módulo LoRA**: adapta estrategias al entorno de ejecución.
- **Cliente Kraken (ccxt)**: ejecuta órdenes en tiempo real.
- **Módulo de Monitoreo**: analiza el mercado y ajusta decisiones.
- **Archivos de configuración**: manejo seguro de claves API.

---

## 3. 🧬 Estructura del Proyecto

```

AegisIA/
├── config/
│   └── api\_keys.env                # Claves API (Kraken)
├── models/
│   └── model\_weights/             # Pesos del modelo entrenado
├── chat/
│   └── chat\_interface.py          # Comunicación con la IA
├── trading/
│   ├── kraken\_client.py           # Cliente Kraken
│   ├── lora\_executor.py           # Ejecutor de estrategias LoRA
│   └── strategy\_manager.py        # Aplicador de estrategias IA
├── utils/
│   └── indicators.py              # Indicadores técnicos (opcional)
├── main.py                        # Script principal del sistema

````

---

## 4. 🔁 Flujo de Trabajo

1. El usuario inicia una conversación a través de la app.
2. La entrada es interpretada por el modelo de IA.
3. Se genera una estrategia de trading basada en datos actuales.
4. El módulo LoRA traduce la estrategia en comandos ejecutables.
5. Se envían órdenes a la API de Kraken.
6. El módulo de monitoreo ajusta las estrategias en tiempo real.
7. Se devuelven sugerencias y actualizaciones al usuario por chat.

---

## 5. 💻 Código Base

### `models/load_model.py`

```python
from transformers import AutoTokenizer, AutoModelForCausalLM

def load_chat_model(model_path="models/model_weights"):
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(model_path)
    return tokenizer, model
````

### `chat/chat_interface.py`

```python
from models.load_model import load_chat_model

tokenizer, model = load_chat_model()

def generar_respuesta(input_text):
    inputs = tokenizer(input_text, return_tensors="pt")
    outputs = model.generate(**inputs, max_new_tokens=150)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)
```

### `trading/kraken_client.py`

```python
import ccxt
from dotenv import load_dotenv
import os

load_dotenv("config/api_keys.env")

kraken = ccxt.kraken({
    'apiKey': os.getenv("KRAKEN_API_KEY"),
    'secret': os.getenv("KRAKEN_API_SECRET")
})

def place_order(symbol, side, amount, type='market'):
    return kraken.create_order(symbol=symbol, type=type, side=side, amount=amount)

def get_market_data(symbol="BTC/USD"):
    return kraken.fetch_ticker(symbol)
```

### `trading/lora_executor.py`

```python
def ejecutar_lora_comando(estrategia, datos_mercado):
    print(f"[LoRA] Ejecutando estrategia: {estrategia} con datos: {datos_mercado}")
```

### `trading/strategy_manager.py`

```python
from trading.kraken_client import get_market_data, place_order
from trading.lora_executor import ejecutar_lora_comando

def aplicar_estrategia_ia(respuesta_chat):
    datos = get_market_data()
    if "comprar" in respuesta_chat:
        ejecutar_lora_comando("BUY", datos)
        place_order("BTC/USD", "buy", 0.01)
    elif "vender" in respuesta_chat:
        ejecutar_lora_comando("SELL", datos)
        place_order("BTC/USD", "sell", 0.01)
```

### `main.py`

```python
from chat.chat_interface import generar_respuesta
from trading.strategy_manager import aplicar_estrategia_ia

while True:
    user_input = input("Usuario: ")
    if user_input.lower() in ["salir", "exit"]:
        break
    respuesta = generar_respuesta(user_input)
    print("IA:", respuesta)
    aplicar_estrategia_ia(respuesta)
```

### `config/api_keys.env`

```
KRAKEN_API_KEY=tu_api_key
KRAKEN_API_SECRET=tu_api_secret
```

---

## 6. 📦 Requisitos

Archivo: `requirements.txt`

```
transformers
torch
python-dotenv
krakenex
ccxt
pandas
numpy
```

---

## 7. 🔐 Consideraciones de Seguridad

* Almacenar las claves API en archivos `.env` no expuestos.
* Validar cada estrategia antes de ejecutarla automáticamente.
* Permitir control total del usuario sobre cada orden ejecutada.
* Limitar riesgos y validar límites de operación.

---

