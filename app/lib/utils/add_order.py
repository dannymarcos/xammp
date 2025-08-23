"""
	add_order lo usa ambos bots para poder comprar/vender con los exchange

	IMPORTANTE: Este codigo esta creado para usarse unicamente para los BOTS
"""

import logging
from app.lib.utils.orders.kraken_spot import process_order as process_kraken_spot
from app.lib.utils.orders.bingx import process_order as process_bingx
from app.lib.utils.orders.kraken_futures import process_order as process_kraken_futures
from app.models.trades import set_trade_actual_profit_in_usd
from app.viewmodels.wallet.found import Wallet, WalletAdmin

logger = logging.getLogger(__name__)

def add_order(user_id: int, data: dict, trading_mode: str) -> tuple[bool, float]:
  try:
    print(f"[add_order] user_id={user_id}")
    print(f"[add_order] trading_mode={trading_mode}")
    print(f"[add_order] data={data}")
    wallet_admin = WalletAdmin()
    wallet = Wallet(user_id=user_id)

    isSuccess = False;
    
    if trading_mode == "kraken_spot":
      isSuccess, _ = process_kraken_spot(user_id, data)
    elif trading_mode in ["bingx_spot", "bingx_futures"]:
      isSuccess, _ = process_bingx(user_id, data, trading_mode)
    elif trading_mode == "kraken_futures":
      isSuccess, _ = process_kraken_futures(user_id, data)
    else:
      logger.error(f"Invalid trading mode: {trading_mode}")
      return False, 0.00
    
    if not isSuccess:
      print("ERROR")
      return False, 0.00
    
    user_is_usdt_amount = wallet.get_blocked_balance(
      by_bot=data["order_made_by"],
      currency="BTC/USDT",
      finished=True
    )["amount_usdt"]

    if data.get("orderDirection") == "sell":
      if user_is_usdt_amount >= 0:
        print("ganancias:", user_is_usdt_amount)
      else:
        print("perdidas:", user_is_usdt_amount)

      wallet_admin.add_found(user_id, user_is_usdt_amount, "USDT", "general")
      set_trade_actual_profit_in_usd(trade_id="last", profit_in_usd=user_is_usdt_amount, user_id=user_id, by=data["order_made_by"])

    return True, user_is_usdt_amount
  except Exception as e:
    logger.error(f"Unhandled error in add_order: {str(e)}")
    return False, 0.00
