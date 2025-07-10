from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.iu.routes.utils.utils import get_translated_text
from app.viewmodels.wallet.found import Wallet
import logging

wallet_bp = Blueprint('wallet', __name__)
logger = logging.getLogger(__name__)

@wallet_bp.route("/wallet", methods=['GET', 'POST'])
@login_required
def home_wallet():
    name = current_user.full_name
    id = current_user.id

    wallet = Wallet(id)
    balance = wallet.get_balance()  # Get only general wallet balance
    balance_general = wallet.get_balance("general")  # Get only general wallet balance
    
    # Calculate performance metrics
    performance = wallet.get_accumulated_performance("USDT")
    initial_capital = wallet.get_initial_capital("USDT")

    # Calculate pending balance (transactions with verification=False)
    pending_balance = wallet.get_pending_balance("USDT")
    
    print(balance_general)

    if request.method == 'GET':
        return render_template("wallet.html", 
                             name=name, 
                             balance=balance,
                             balance_general=balance_general,
                             performance=performance,
                             initial_capital=initial_capital,
                             pending_balance=pending_balance,
                             is_admin=(current_user.role == "admin"))
    return render_template("under_construction.html")

@wallet_bp.route("/settings/wallet", methods=["GET", "POST"])
@login_required
def settings_wallet_route():
    try:
        return render_template("settings/wallet.html", user=current_user, get_translated_text=get_translated_text)
    except Exception as e:
        logger.error(f"Error in wallet settings: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@wallet_bp.route("/add_found_wallet", methods=["POST"])
@login_required
def add_found_wallets():
    user_id = current_user.id
    amount = request.form.get("amount")
    symbol = "USDT"
    ref = request.form.get("ref")
    red = "BEP-20" # request.form.get("red")

    wallet = Wallet(user_id)
    pending_balance = wallet.get_pending_balance("USDT")
    if pending_balance > 0:
        return jsonify({"success": False, "error": "Pending balance is greater than 0", "pending_balance": pending_balance})

    if (amount is None) or (ref is None):
        return jsonify({"success": False, "error": "it's empty"})

    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid amount format"})

    wallet = Wallet(user_id)
    result = wallet.deposit_found_wallet(amount, symbol, ref, red, "general")

    if not result:
        return jsonify({"success": False, "error": "not save in db"})

    return jsonify({"success": True})

@wallet_bp.route("/get_found_wallets", methods=["GET"])
@login_required
def get_found_wallets():
    user_id = current_user.id
    wallet = Wallet(user_id)
    founds = wallet.get_found_wallets()
    return jsonify({"success": True, "founds": founds})

@wallet_bp.route("/api/wallet/chart-data", methods=["GET"])
@login_required
def get_wallet_chart_data():
    """
    Get chart data for wallet earnings/losses over time
    Returns JSON with labels and datasets for Chart.js
    """
    try:
        user_id = current_user.id
        wallet = Wallet(user_id)
        
        # Get chart data from wallet class
        chart_data_raw = wallet.get_chart_data(days=1)
        
        # Format data for Chart.js
        chart_data = {
            "labels": chart_data_raw["labels"],
            "datasets": [
                {
                    "label": "Ganancias",
                    "data": chart_data_raw["earnings_data"],
                    "borderColor": "rgb(75, 192, 192)",
                    "backgroundColor": "rgba(75, 192, 192, 0.2)",
                    "borderWidth": 2,
                    "tension": 0.1
                },
                {
                    "label": "Pérdidas",
                    "data": chart_data_raw["losses_data"],
                    "borderColor": "rgb(255, 99, 132)",
                    "backgroundColor": "rgba(255, 99, 132, 0.2)",
                    "borderWidth": 2,
                    "tension": 0.1
                }
            ]
        }
        
        return jsonify({
            "success": True,
            "data": chart_data
        })
        
    except Exception as e:
        logger.error(f"Error getting wallet chart data: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500