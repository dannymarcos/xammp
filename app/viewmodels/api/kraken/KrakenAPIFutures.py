from app.viewmodels.api.kraken.KrakenAPI import KrakenAPI
import json
import uuid
import requests
import logging
from app.viewmodels.services.GenerateApiSign import GenerateApiSign
logger = logging.getLogger(__name__)
class KrakenAPIFutures(KrakenAPI):
  def __init__(self):
    super().__init__("futures", "https://futures.kraken.com")
    self._add_order_endpoint = f"{self._endpoint}/derivatives/api/v3/sendOrder"

  def add_order(self, order_type, order_direction, volume, symbol, price_limit):
       pass