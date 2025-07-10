from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
import logging
from functools import wraps
from datetime import datetime

from app.viewmodels.wallet.found import WalletAdmin

admin_bp = Blueprint('admin', __name__)
logger = logging.getLogger(__name__)

wallet = WalletAdmin()

def admin_required(f):
    """Decorator to check if the current user is an admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(404)  # Unauthorized
        if current_user.role != "admin":
            abort(404)  # Forbidden - not admin
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route("/admin/panel")
@login_required
@admin_required
def admin_route():
    """Admin panel page route"""
    tx = wallet.get_list_founds(page=1)
    
    # Balances are now loaded dynamically via JavaScript
    return render_template("admin/panel.html", transations=tx)

@admin_bp.route("/admin/verify-transaction", methods=["POST"])
@login_required
@admin_required
def admin_verify_transaction():
    """Admin verify transaction route"""
    data = request.get_json()
    id = data.get("transaction_id")

    is_valid = wallet.set_verification(id, True)
    data = wallet.get_data_with_id(id)

    print(data)

    wallet.add_found(data.user_id, data.amount, data.currency, "general")
    return jsonify({"success": is_valid})

@admin_bp.route("/admin/real-balances", methods=["GET"])
@login_required
@admin_required
def get_real_master_balances():
    """Get real master account balances from exchange APIs"""
    try:
        real_balances = wallet.get_real_master_account_balances()
        return jsonify({
            "success": True,
            "data": real_balances,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting real master balances: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@admin_bp.route("/admin/real-balances-summary", methods=["GET"])
@login_required
@admin_required
def get_real_master_balance_summary():
    """Get summary of real master account balances with USDT totals"""
    try:
        summary = wallet.get_real_master_balance_summary()
        return jsonify({
            "success": True,
            "data": summary,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting real master balance summary: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@admin_bp.route("/admin/refresh-balances", methods=["POST"])
@login_required
@admin_required
def refresh_real_balances():
    """Force refresh of real master account balances"""
    try:
        # Get both detailed balances and summary
        real_balances = wallet.get_real_master_account_balances()
        summary = wallet.get_real_master_balance_summary()
        
        return jsonify({
            "success": True,
            "detailed_balances": real_balances,
            "summary": summary,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error refreshing real balances: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
