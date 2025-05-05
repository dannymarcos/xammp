# app/viewmodels/api/spot/KrakenSpotAPI
import requests
import logging
from flask import jsonify

logger = logging.getLogger(__name__)

class KrakenSpotAPI:

    def __init__(self):

        self.__endpoint = "https://api.kraken.com/0/public/Ticker"
        self.data = None

    def get_ticker_kraken(self):
        try:
            response = requests.get(self.__endpoint)
            if response.status_code != 200:
                logger.error(f"Error fetching tickers: HTTP {response.status_code}")
                return jsonify({"error": "Failed to fetch tickers"}), 500

            self.data = response.json()
            if "error" in self.data and self.data["error"]:
                logger.error(f"Kraken API error: {self.data['error']}")
                return {"error": str(self.data["error"])}, 500

        except Exception as e:
            logger.error(f"Error getting cryptocurrencies: {e}")
            return {"error": str(e)}, 500
        
        return self.data, 200
        
    def get_symbol_and_ultimate_price_trade(self):
        if not self.data:
            logger.error("No data available for symbol and price processing")
            return {"error":"No data available"}, 500
            
        try:
            result = self.data.get("result", {})
            if not result:
                logger.warning("Empty result set from Kraken API")
                return {"cryptos": []}, 200
                
            cryptos = []
            logger.debug(f"Processing {len(result.items())} trading pairs")

            for pair_name, ticker_info in result.items():
                if "c" in ticker_info:  # "c" contains the last trade closed price
                    price = ticker_info["c"][0]  # First element is the price
                    logger.debug(f"Processing pair {pair_name} with price {price}")
                    cryptos.append({
                        "symbol": pair_name,
                        "price": price
                    })
                else:
                    logger.warning(f"Pair {pair_name} missing 'c' (close price) field")

            logger.info(f"Successfully processed {len(cryptos)} crypto pairs")
            return {"cryptos": cryptos}, 200
            
        except Exception as e:
            logger.error(f"Error processing symbol data: {e}", exc_info=True)
            return {"error": str(e)}, 500
