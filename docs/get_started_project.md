
---

📄 **`docs/get_started_project.md`**

# 🚀 Guía de Inicio Rápido
Este documento explica cómo configurar y ejecutar el proyecto de forma eficiente.

---

## Prerrequisitos
- Python (3.9 - 3.12)
- Git

> ⚠️ Python 3.13.x no es compatible con el proyecto debido a que no tiene soporte oficial a tensorflow
---

## 1. Configuración Inicial del Entorno

<details>
  <summary>
    <strong>Windows</strong>
  </summary>

  ```bash
  # Crear entorno virtual
  python -m venv .venv

  # Activar entorno
  .\.venv\Scripts\activate
  ```

</details>

<details>
  <summary>
    <strong>Linux/macOS</strong>
  </summary>

  ```bash
  # Crear entorno virtual
  python3 -m venv .venv

  # Activar entorno
  source .venv/bin/activate
  ```

</details>

<br />

> 💡 **Importante**: Debes activar el entorno cada vez que trabajes en el proyecto.

---

## 2. Instalación de Poetry

[Poetry](https://python-poetry.org/) es un gestor de dependencias moderno que reemplaza a pip. Instálalo con:

```bash
pip install --upgrade pip
pip install poetry
```

Verifica la instalación:
```bash
poetry --version
```

---

## 3. Instalación de Dependencias

Con Poetry, instala todas las dependencias del proyecto:

```bash
poetry install
```

Esto:
1. Creará un entorno virtual aislado (si no existe)
2. Instalará todas las dependencias del `pyproject.toml`
3. Generará un `poetry.lock` para versiones exactas

> 👀 Si no tienes una tarjeta grafica dedicada es posible que la libreria tensorflow te de error (es poco común este error)

<details>
  <summary>
  <strong>Solucionar el error de la instalación de tensorflow</strong>
</summary>

  Este error es debido a que se necesita instalar una versión que funcione solamente con la **CPU**, entonces para Python **3.12** podriamos instalarlo con los siguientes comandos:

  ```bash
  # Linux x86_64
  pip install --upgrade https://storage.googleapis.com/tensorflow/versions/2.19.0/tensorflow_cpu-2.19.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl
  ```

  ```bash
  # Windows
  pip install --upgrade https://storage.googleapis.com/tensorflow/versions/2.19.0/tensorflow-2.19.0-cp312-cp312-win_amd64.whl
  ```
  > Los links se puede obtener en [la documentación de tensorflow](https://www.tensorflow.org/install/pip#package_location)

</details>

---

## 4. Configuración del Entorno (.env)

Crea un archivo `.env` en la raíz del proyecto con estos valores mínimos:

```env
# .env

# Flask Configuratin
ENVIRONMENT="local"

SECRET_KEY='generate_a_strong_random_secret_key_here' # Important for session security

# Database Configuration
# Example for MySQL (adjust user, password, host, dbname as needed)
# SQLALCHEMY_DATABASE_URI='mysql+pymysql://root:root@localhost/xampp22'
# Example for SQLite (relative path)
SQLALCHEMY_DATABASE_URI=

# Optional Trading Parameters (can override defaults in config.py if the code is modified to read them)
# TRADING_MODE='spot'
# SYMBOL='XBTUSD'

TELEGRAM_BOT_TOKEN=""
TELEGRAM_BOT_USERNAME="" 

KRAKEN_API_KEY=
KRAKEN_API_SECRET=
KRAKEN_FUTURE_API_KEY=
KRAKEN_FUTURE_API_SECRET=

KRAKEN_SPOT_API_KEY=
KRAKEN_SPOT_API_SECRET=

BINGX_API_KEY=
BINGX_API_SECRET=
BINGX_API_KEY_FUTURES=
BINGX_API_SECRET_FUTURES=

```

Si no configuras `SQLALCHEMY_DATABASE_URI`:
- Se usará `sqlite:///instance/your_database.db`
- La carpeta `instance` se creará automáticamente
- La base de datos se generará al iniciar la aplicación

---

## 5. Ejecutar la Aplicación

#### Opción 1: Con Poetry
```bash
poetry run python main.py
```

#### Opción 2: Con entorno virtual activado
```bash
python main.py
```

---


## 🛠 Estructura del Proyecto

```
aegis-trading-platform/
├── app/               # Código fuente principal
├── instance/          # Base de datos (generada automáticamente)
├── migrations/        # Migraciones
├── tests/             # Pruebas (proximamente)
├── .env               # Variables de entorno
├── .gitignore
├── main.py            # Punto de entrada
├── poetry.lock        # Lock file de dependencias
└── pyproject.toml     # Configuración de Poetry
└── Aegis-IA0003.keras # Modelo que usa tensorflow
```