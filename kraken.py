import ccxt
API_KEY = 'lrF2TQ9KL+fli892UdhFQmhoG5aSK8s/2KOcXXRs8ZrllE8Mty4XOD5L'
API_SECRET = 'fDSzd8zT/iQZFBHPKSebJtu7FDyF5nKPAGWX3/udmt6jfi+nw8U6/O2YVulon3RRPA83oVdowo2r+UMJznsZk2KY'
# --- CONFIGURACIÓN DEL EXCHANGE ---
exchange = ccxt.krakenfutures({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
})

import http.client
import urllib.request
import urllib.parse
import hashlib
import hmac
import base64

def main():
   response = request(
      method = "GET",
      path = "/derivatives/api/v3/tickers",
      environment = "https://futures.kraken.com",
   )
   response = request(
      method = "POST",
      path = "/derivatives/api/v3/sendorder",
       body = {
         "orderType": "post",
         "symbol": "PF_RENDERUSD",
         "side": "buy",
         "size": "1",
         "limitPrice": "1",
      },
      public_key = "lrF2TQ9KL+fli892UdhFQmhoG5aSK8s/2KOcXXRs8ZrllE8Mty4XOD5L",
      private_key = "fDSzd8zT/iQZFBHPKSebJtu7FDyF5nKPAGWX3/udmt6jfi+nw8U6/O2YVulon3RRPA83oVdowo2r+UMJznsZk2KY",
      environment = "https://futures.kraken.com",
   )
   print(response.read().decode())
   print('Obteniendo saldo disponible en Kraken Futures...')
   balance = exchange.fetch_balance()
   print('Saldo disponible:')
   for currency, info in balance['total'].items():
        print(f"{currency}: {info}")

def request(method: str = "GET", path: str = "", query: dict | None = None, body: dict | None = None, nonce: str = "", public_key: str = "", private_key: str = "", environment: str = "") -> http.client.HTTPResponse:
   url = environment + path
   query_str = ""
   if query is not None and len(query) > 0:
      query_str = urllib.parse.urlencode(query)
      url += "?" + query_str
   body_str = ""
   if body is not None and len(body) > 0:
      body_str = urllib.parse.urlencode(body)
   headers = {}
   if len(public_key) > 0:
      headers["APIKey"] = public_key
      headers["Authent"] = get_signature(private_key, query_str+body_str, nonce, path)
      if len(nonce) > 0:
         headers["Nonce"] = nonce
   req = urllib.request.Request(
      method=method,
      url=url,
      data=body_str.encode(),
      headers=headers,
   )
   return urllib.request.urlopen(req)

def get_signature(private_key: str, data: str, nonce: str, path: str) -> str:
   return sign(
      private_key=private_key,
      message=hashlib.sha256(
         (data + nonce + path.removeprefix("/derivatives")).encode()
      ).digest()
   )

def sign(private_key: str, message: bytes) -> str:
   return base64.b64encode(
      hmac.new(
         key=base64.b64decode(private_key),
         msg=message,
         digestmod=hashlib.sha512,
      ).digest()
   ).decode()

if __name__ == "__main__":
   main()