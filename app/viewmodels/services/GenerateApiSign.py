import json
import hashlib
import hmac
import base64

class GenerateApiSign:
    def __init__(self):
        self.__apiSign = None

    def generate_api_sign(self,  url_path, data, api_secret):
        """
        Genera el API-Sign requerido por Kraken.

        Pasos básicos (consulta la documentación de Kraken para más detalles):
          1. Concatenar el nonce y el payload (data) en una cadena.
          2. Hacer un hash SHA256 de esa cadena.
          3. Concatenar el path de la API (por ejemplo, '/0/private/AddOrder') con el hash obtenido.
          4. Usar HMAC SHA512 con la clave secreta (decodificada de base64) para firmar el resultado.
          5. Codificar el resultado en base64.
        """

        postdata = '&'.join([f"{key}={value}" for key, value in data.items()])
        # Paso 1: extraer el nonce
        nonce = str(data["nonce"]).encode()
        # Paso 2: hash SHA256
        hash_digest = hashlib.sha256(nonce + postdata.encode()).digest()
        # Paso 3: concatenar path y hash
        message = url_path.encode() + hash_digest
        # Paso 4: HMAC SHA512 con el API secret
        secret_decoded = base64.b64decode(api_secret)
        hmac_digest = hmac.new(secret_decoded, message, hashlib.sha512).digest()
        # Paso 5: codificar en base64
        api_sign = base64.b64encode(hmac_digest)
        return api_sign.decode()
           